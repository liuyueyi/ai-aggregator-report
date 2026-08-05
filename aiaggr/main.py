from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from .config import (
    ROOT,
    enabled_topics,
    llm_settings,
    load_config,
    report_dir,
    state_dir,
    timezone_name,
)
from .classifier import classify
from .dedup import aggregate
from .deep import enrich_with_content
from .fetchers import select_fetchers
from .fetchers.base import Signal
from .notify import build_feishu_card, feishu_webhook_urls, send_feishu
from .pipeline import generate_topic_report
from .renderer import date_path, report_exists, save_index, save_report
from .state import StateStore

_HTTP_TIMEOUT = 30.0

# --json 模式：进度日志路由到 stderr，stdout 仅输出结果 JSON（供 AI Agent/脚本消费）
_JSON_MODE = False


def _today(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")


async def fetch_all(fetchers: dict) -> tuple[list[Signal], list[str]]:
    """并发抓取全部源，返回 (signals, 空结果/失败源 key 列表)。"""
    async with httpx.AsyncClient(follow_redirects=True, timeout=_HTTP_TIMEOUT) as client:
        tasks = [f.safe_fetch(client) for f in fetchers.values()]
        results = await asyncio.gather(*tasks)
    signals: list[Signal] = []
    empty: list[str] = []
    for key, r in zip(fetchers.keys(), results):
        if r:
            signals.extend(r)
        else:
            empty.append(key)
    return signals, empty


def _apply_global_limit(fetchers: dict, limit: int | None) -> None:
    if not limit:
        return
    for f in fetchers.values():
        f.config["limit"] = limit


def _resolve_topics(args, cfg) -> dict:
    topics = enabled_topics(cfg)
    if args.topic:
        keys = [t.strip() for t in args.topic.split(",") if t.strip()]
        topics = {k: v for k, v in topics.items() if k in keys}
    return topics


def _pending_topics(topics, date, rdir, force: bool) -> list[str]:
    if force:
        return list(topics)
    return [t for t in topics if not report_exists(t, date, rdir)]


def _build_site(cfg, rdir) -> None:
    """按 config.site 生成 Web UI 数据（manifest.json）与 RSS（feed.xml）。"""
    site_cfg = cfg.get("site", {})
    if not site_cfg.get("enabled", True):
        return
    base_url = os.environ.get("PAGES_URL") or site_cfg.get("base_url", "") or ""
    from .config import site_dir
    from .site import build_site

    build_site(rdir, site_dir(cfg), base_url, enabled_topics(cfg))


def _topic_entry(tkey, tconf, *, tagline="", file=None, count=0, skipped=False) -> dict:
    return {
        "key": tkey,
        "name": tconf.get("name", tkey),
        "icon": tconf.get("icon", ""),
        "tagline": tagline,
        "file": file,
        "count": count,
        "skipped": skipped,
    }


def _collect_signal(s: Signal) -> dict:
    """采集模式输出用的信号序列化（含 Agent 写日报所需字段）。"""
    return {
        "source": s.source,
        "source_key": s.source_key,
        "title": s.title,
        "url": s.url,
        "heat": s.heat,
        "score": round(s.score, 2),
        "raw_score": s.raw_score,
        "comments": s.comments,
        "author": s.author,
        "summary": s.summary,
        "content": s.content,
        "tags": s.tags,
        "published_at": s.published_at,
        "age_bucket": s.age_bucket,
        "hn_url": s.hn_url,
        "gh_url": s.gh_url,
        "also_on": s.extra.get("also_on", []),
        "project": s.extra.get("project", ""),
        "repo": s.extra.get("repo", ""),
        "kind": s.extra.get("kind", ""),
    }


async def _collect(topics, pools, state, date, cross_day_exclude: bool, base: dict,
                   tracking: dict[str, list[Signal]] | None = None,
                   deep: bool = False) -> dict:
    """采集模式：只抓取+去重+规则分类，把按主题分组的信号 JSON 交给上层（Agent/LLM），
    本身不生成日报、不调用 LLM。仍需记录本次接入信号的指纹以维持跨日去重。"""
    topic_pools: dict[str, list[Signal]] = {}
    emitted: list[Signal] = []
    for tkey in topics:
        tconf = topics[tkey]
        pool = pools.get(tkey, [])
        if cross_day_exclude:
            pool = [s for s in pool if not s.seen_on]
        limit = int(tconf.get("limit", 15))
        pool_sorted = sorted(pool, key=lambda s: s.score, reverse=True)[:limit]
        topic_pools[tkey] = pool_sorted
        emitted.extend(pool_sorted)

    # --deep：为每个主题 TOP-N 信号拉取正文（并发），供 Agent 写深度洞察
    if deep and emitted:
        print(f"→ --deep 正文抓取 {len(emitted)} 条信号（并发） ...")
        await enrich_with_content(emitted)

    topic_signals: dict[str, list[dict]] = {
        tkey: [_collect_signal(s) for s in sigs] for tkey, sigs in topic_pools.items()
    }

    new_fps = 0
    if emitted:
        new_fps = state.record_emitted(emitted, date)
    total = sum(len(v) for v in topic_signals.values())
    for tkey, sigs in topic_signals.items():
        print(f"→ [{tkey}] 采集 {len(sigs)} 条信号")

    tracking_out: dict[str, list[dict]] = {}
    for k, sigs in (tracking or {}).items():
        if sigs:
            tracking_out[k] = [_collect_signal(s) for s in sigs]
    if tracking_out:
        print(f"✓ 生态追踪信号：{' / '.join(f'{k}={len(v)}' for k, v in tracking_out.items())}")

    print(f"✓ 采集模式完成：共 {total} 条主题信号（已按主题分组，未生成日报，交由上层处理）")
    result = {
        **base,
        "exit_code": 0,
        "mode": "collect",
        "new_fingerprints": new_fps,
        "signals": total,
        "topics": topic_signals,
    }
    if tracking_out:
        result["tracking"] = tracking_out
    return result


async def amain(args, cfg) -> dict:
    tz = timezone_name(cfg)
    date = args.date or _today(tz)
    topics = _resolve_topics(args, cfg)
    rdir = report_dir(cfg)
    settings = llm_settings(cfg)
    if args.mock_llm:
        settings["mock"] = True

    base = {
        "exit_code": 0,
        "date": date,
        "mode": "mock" if settings["mock"] else "llm",
    }

    # ---- 幂等：无待生成主题且未 --force 时直接结束（采集模式跳过该检查） ----
    pending = _pending_topics(topics, date, rdir, args.force)
    if not args.collect and not pending:
        entries = [
            _topic_entry(k, v, tagline="（已存在）",
                         file=str((date_path(rdir, date) / f"{k}.md").relative_to(ROOT)),
                         skipped=True)
            for k, v in topics.items()
        ]
        print(f"✓ {date} 所有主题日报已存在（{', '.join(topics)}）。用 --force 强制重跑。")
        return {**base, "skipped": True, "topics": entries,
                "message": "all topic reports already exist"}

    if not args.collect and args.force:
        print(f"→ --force 触发，将重跑 {', '.join(pending)}")
    elif not args.collect:
        _ = [topics.pop(t, None) for t in list(topics) if t not in pending]
        print(f"→ 待生成主题: {', '.join(topics)}")

    print(f"=== AI 聚合日报 · {date} ===")

    # ---- 采集 ----
    requested_sources = (
        [s.strip() for s in args.source.split(",") if s.strip()] if args.source else None
    )
    fetchers = select_fetchers(cfg, requested_sources)
    if not fetchers:
        print("✗ 未选中任何数据源（检查 --source / config enabled）。")
        return {**base, "exit_code": 2, "error": "no sources selected"}
    _apply_global_limit(fetchers, args.limit)
    print(f"→ 并行抓取 {len(fetchers)} 个数据源 ...")
    signals, sources_empty = await fetch_all(fetchers)
    print(f"✓ 抓取到 {len(signals)} 条原始信号")
    if not signals:
        return {**base, "exit_code": 1, "error": "no signals fetched",
                "sources": len(fetchers), "sources_empty": sources_empty}
    base["sources"] = len(fetchers)
    base["sources_empty"] = sources_empty

    # 生态追踪信号单独分区（不参与主题日报，专供 ai-cli / ai-agents 专题报告）
    tracking_signals: dict[str, list[Signal]] = {
        k: [s for s in signals if s.source_key == k]
        for k in ("cli_tracker", "agents_tracker")
    }

    # ---- 同日去重 + 分数叠加 ----
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    aggregated = aggregate(
        signals,
        today=date_obj,
        ignore_tracking=cfg.get("dedup", {}).get("ignore_tracking", True),
    )
    print(f"✓ 聚合去重后 {len(aggregated)} 条唯一信号")
    base["fetched"] = len(signals)
    base["unique"] = len(aggregated)

    # ---- 跨日去重 ----
    state = StateStore(
        state_dir(cfg),
        window_days=int(cfg.get("dedup", {}).get("window_days", 7)),
    )
    aggregated = state.mark_seen(aggregated, date)

    # ---- 主题分类 ----
    pools = classify(aggregated, topics, settings, use_llm=(not args.no_llm and not args.collect))
    pool_counts = {k: len(v) for k, v in pools.items()}
    print(f"✓ 主题分类: {pool_counts}")

    # ---- 采集模式：不生成日报，信号交给上层 ----
    if args.collect:
        cross_day_exclude = cfg.get("dedup", {}).get("cross_day_exclude", True)
        return await _collect(topics, pools, state, date, cross_day_exclude, base,
                              tracking=tracking_signals, deep=args.deep)

    # ---- 逐主题生成日报 ----
    cross_day_exclude = cfg.get("dedup", {}).get("cross_day_exclude", True)
    tagline_map = state.taglines_by_topic(days=int(cfg.get("dedup", {}).get("window_days", 7)))
    prompts_dir = ROOT / "prompts"

    # --deep：生成前为各主题 TOP-N 信号拉取正文（跨主题去重后并发），供 LLM 写深度洞察
    if args.deep:
        deep_picks: list[Signal] = []
        seen_ids: set[int] = set()
        for tkey in topics:
            tconf = topics[tkey]
            pool = pools.get(tkey, [])
            if cross_day_exclude:
                pool = [s for s in pool if not s.seen_on]
            for s in sorted(pool, key=lambda x: x.score, reverse=True)[: int(tconf.get("limit", 15))]:
                if id(s) not in seen_ids:
                    seen_ids.add(id(s))
                    deep_picks.append(s)
        if deep_picks:
            print(f"→ --deep 正文抓取 {len(deep_picks)} 条信号（并发） ...")
            await enrich_with_content(deep_picks)

    saved_files = []
    topic_entries = []
    emitted: list[Signal] = []
    for tkey in topics:
        tconf = topics[tkey]
        pool = pools.get(tkey, [])
        if cross_day_exclude:
            pool = [s for s in pool if not s.seen_on]
        if not pool:
            print(f"✗ [{tkey}] 无可用信号（可能已被跨日去重排除），跳过")
            topic_entries.append(_topic_entry(tkey, tconf, tagline="（无信号）", skipped=True))
            continue
        limit = int(tconf.get("limit", 15))
        pool_sorted = sorted(pool, key=lambda s: s.score, reverse=True)[:limit]
        recent = tagline_map.get(tkey, [])
        result = await generate_topic_report(
            tkey, tconf, pool_sorted, date, recent, settings, prompts_dir
        )
        markdown = result.get("markdown")
        if not markdown:
            print(f"✗ [{tkey}] 生成失败且兜底为空，跳过")
            topic_entries.append(_topic_entry(tkey, tconf, tagline="（生成失败）", skipped=True))
            continue
        path = save_report(markdown, tkey, date, rdir)
        saved_files.append(path)
        topic_entries.append(
            _topic_entry(
                tkey, tconf,
                tagline=result.get("tagline", ""),
                file=str(path.relative_to(ROOT)),
                count=len(pool_sorted),
            )
        )
        state.append_tagline(date, tkey, result.get("tagline", ""))
        emitted.extend(pool_sorted)
        print(f"✓ [{tkey}] 已保存到 {path.relative_to(ROOT)}")

    # ---- 生态追踪专题报告（ai-cli / ai-agents）----
    if not args.collect:
        from .tracking import generate_tracking_reports

        saved_files.extend(
            await generate_tracking_reports(tracking_signals, settings, date, prompts_dir, rdir)
        )

    if not saved_files:
        print("✗ 主题日报全部失败，不更新状态。")
        return {**base, "exit_code": 1, "error": "all topic reports failed",
                "topics": topic_entries}

    # ---- 幂等状态落盘 + 索引 ----
    new_fps = 0
    if emitted:
        new_fps = state.record_emitted(emitted, date)
        print(f"✓ 记录 {new_fps} 条新信号指纹到 seen（跨日去重）")
    index_path = save_index(date, topic_entries, rdir)
    print(f"✓ 当日索引已保存到 {date_path(rdir, date) / 'index.md'}")
    print(f"→ 完成：{len(saved_files)} 份主题日报写入 {rdir}")

    # ---- 站点产物（manifest + RSS）与飞书推送 ----
    if not args.collect:
        _build_site(cfg, rdir)
        if feishu_webhook_urls():
            title, content = build_feishu_card(date, topic_entries)
            await send_feishu(title, content)

    return {
        **base,
        "exit_code": 0,
        "topics": topic_entries,
        "index": str(index_path.relative_to(ROOT)),
        "report_dir": str(rdir.relative_to(ROOT)),
        "new_fingerprints": new_fps,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aiaggr",
        description="AI 聚合日报：多源采集 → 去重幂等 → 主题分类 → 每日多主题日报",
    )
    p.add_argument("--date", help="报告日期 YYYY-MM-DD（默认今天，按配置时区）")
    p.add_argument("--topic", help="只看指定主题（逗号分隔，默认全部）")
    p.add_argument("--source", help="数据源 key（逗号分隔；默认 all；支持 user/opml 自定义源）")
    p.add_argument("--limit", type=int, help="覆盖每个数据源的抓取条数上限")
    p.add_argument("--force", action="store_true", help="强制重跑，覆盖已存在的日报")
    p.add_argument("--mock-llm", action="store_true", help="模拟 LLM（无需 key 跑通管线）")
    p.add_argument("--collect", action="store_true",
                   help="采集模式：只抓取+去重+规则分类，stdout 输出按主题分组的信号 JSON，"
                        "不调用 LLM、不生成日报（配合 --json 供上层 Agent 写日报）")
    p.add_argument("--deep", action="store_true",
                   help="为每条信号抓取正文（截断至 ~3000 字），供 Agent / LLM 写深度洞察"
                        "（--collect 与全量 LLM 模式均可用；网络受限源会自动跳过）")
    p.add_argument("--no-llm", dest="no_llm", action="store_true",
                   help="跳过 LLM 主题精修（仅用规则分类）")
    p.add_argument("--json", action="store_true",
                   help="Agent 友好输出：进度日志进 stderr，stdout 只输出结果 JSON")
    p.add_argument("--list-sources", action="store_true", help="列出所有数据源")
    p.add_argument("--config", help="config.yaml 路径（默认项目根目录）")
    return p


async def arun(args) -> dict:
    cfg = load_config(args.config)
    if args.list_sources:
        fetchers = select_fetchers(cfg)
        for key in sorted(fetchers):
            print(key)
        return {"exit_code": 0, "sources": sorted(fetchers)}
    return await amain(args, cfg)


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args()

    global _JSON_MODE
    _JSON_MODE = args.json
    if args.json:
        # 所有进度/诊断日志进 stderr，stdout 保留给结果 JSON
        sys.stdout = sys.stderr

    try:
        result = asyncio.run(arun(args))
    except KeyboardInterrupt:
        result = {"exit_code": 130, "error": "interrupted"}
    except Exception as e:  # noqa: BLE001
        result = {"exit_code": 1, "error": f"{type(e).__name__}: {e}"}

    if _JSON_MODE:
        sys.__stdout__.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif result.get("error"):
        print(f"✗ 运行失败: {result['error']}")

    sys.exit(int(result.get("exit_code", 1)))


if __name__ == "__main__":
    main()