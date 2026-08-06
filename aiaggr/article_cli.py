"""AI 文章生产工作流独立入口。

用法:
    python -m aiaggr.article_cli [选项]

示例:
    # 真实 LLM 生成
    python -m aiaggr.article_cli --source hn_ai --topic ai_daily --limit 12

    # mock 冒烟
    python -m aiaggr.article_cli --mock-llm --source toutiao --topic social

    # Agent 模式（JSON stdout）
    python -m aiaggr.article_cli --json --source hn_ai --topic ai_daily
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime

from .config import (
    ROOT,
    article_dir,
    enabled_topics,
    llm_settings,
    load_config,
    promp_dir,
    report_dir,
    state_dir,
    timezone_name,
)
from .dedup import aggregate
from .fetchers import select_fetchers
from .renderer import date_path
from .state import StateStore
from .topics import (
    _compute_diff,
    _load_prev_suggestions,
    generate_topic_suggestions,
    render_topics_md,
)
from .main import fetch_all, _apply_global_limit, _today


def _parse_item_idx(uid: str) -> int:
    try:
        return int(str(uid).lstrip("c"))
    except (TypeError, ValueError):
        return -1


def _requested_sources(args) -> list[str] | None:
    if not args.source:
        return None
    return [s.strip() for s in args.source.split(",") if s.strip()]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aiaggr-article",
        description="AI 文章生产：多源采集 → 聚合去重 → 选题 → 证据 → 计划 → 草稿 → 审稿 → 排版",
    )
    p.add_argument("--date", help="报告日期 YYYY-MM-DD（默认今天，按配置时区）")
    p.add_argument("--topic", help="只看指定主题（逗号分隔，默认全部）")
    p.add_argument("--source", help="数据源 key（逗号分隔；默认 all）")
    p.add_argument("--limit", type=int, help="覆盖每个数据源的抓取条数上限")
    p.add_argument("--mock-llm", action="store_true", help="模拟 LLM（无需 key 跑通管线）")
    p.add_argument("--json", action="store_true",
                   help="Agent 友好输出：进度日志进 stderr，stdout 只输出结果 JSON")
    p.add_argument("--topics-only", action="store_true",
                   help="选题参考模式：读取当日已有日报，LLM 生成选题建议（不抓取、不生成文章）")
    p.add_argument("--config", help="config.yaml 路径（默认项目根目录）")
    return p


async def amain_topics_only(args, cfg) -> dict:
    """选题参考模式：读取当日已有日报 → 逐主题调 LLM → 输出选题建议 Markdown。"""
    tz = timezone_name(cfg)
    date = args.date or _today(tz)
    settings = llm_settings(cfg)
    if args.mock_llm:
        settings["mock"] = True

    if settings["mock"]:
        print("→ LLM: 未启用（mock 模式，不调用模型）")
    elif not settings["api_key"]:
        print("→ LLM: 未配置 LLM_API_KEY（将走确定性兜底产物）")
    else:
        print(f"→ LLM: 已启用 · 模型: {settings['model'] or '(未配置 LLM_MODEL)'}")

    base = {
        "exit_code": 0,
        "date": date,
        "mode": "mock" if settings["mock"] else "llm",
        "workflow": "topics_only",
    }

    print(f"=== 选题参考模式 · {date} ===")

    rdir = report_dir(cfg)
    topics = enabled_topics(cfg)
    if args.topic:
        keys = [t.strip() for t in args.topic.split(",") if t.strip()]
        topics = {k: v for k, v in topics.items() if k in keys}

    prompts_dir = promp_dir(cfg)

    print(f"→ 并发生成 {len(topics)} 个主题的选题建议 ...")
    suggestions = await generate_topic_suggestions(topics, date, rdir, settings, prompts_dir)
    if not suggestions:
        print("✗ 无可用的日报，无法生成选题建议")
        return {**base, "exit_code": 1, "error": "no reports found"}

    # 与前日对比
    prev = _load_prev_suggestions(rdir, date, topics)
    curr_sugs = {k: v.get("suggestions", []) for k, v in suggestions.items()}
    diff = _compute_diff(prev, curr_sugs)

    # 输出 Markdown
    md = render_topics_md(date, suggestions, diff)
    out_dir = date_path(rdir, date)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "topic_suggestions.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"✓ 选题建议已保存: {md_path.relative_to(ROOT)}")

    return {
        **base,
        "topics": suggestions,
        "diff": diff,
        "file": str(md_path.relative_to(ROOT)),
    }


async def amain(args, cfg) -> dict:
    """文章生产工作流主逻辑：抓取 → 聚合 → 跨日去重 → 选题/证据/计划/草稿/审稿/排版。"""
    from .article import build_items, run_article

    tz = timezone_name(cfg)
    date = args.date or _today(tz)
    settings = llm_settings(cfg)
    if args.mock_llm:
        settings["mock"] = True

    if settings["mock"]:
        print("→ LLM: 未启用（mock 模式，不调用模型）")
    elif not settings["api_key"]:
        print("→ LLM: 未配置 LLM_API_KEY（将走确定性兜底产物）")
    else:
        print(f"→ LLM: 已启用 · 模型: {settings['model'] or '(未配置 LLM_MODEL)'}")

    base = {
        "exit_code": 0,
        "date": date,
        "mode": "mock" if settings["mock"] else "llm",
        "workflow": "article",
    }

    print(f"=== 文章生产工作流 · {date} ===")

    fetchers = select_fetchers(cfg, _requested_sources(args))
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

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    aggregated = aggregate(
        signals,
        today=date_obj,
        ignore_tracking=cfg.get("dedup", {}).get("ignore_tracking", True),
    )
    print(f"✓ 聚合去重后 {len(aggregated)} 条唯一信号")

    state = StateStore(
        state_dir(cfg),
        window_days=int(cfg.get("dedup", {}).get("window_days", 7)),
    )
    aggregated = state.mark_seen(aggregated, date)
    cross_day_exclude = cfg.get("dedup", {}).get("cross_day_exclude", True)
    pool = [s for s in aggregated if not s.seen_on] if cross_day_exclude else list(aggregated)
    pool.sort(key=lambda s: s.score, reverse=True)
    input_limit = int(cfg.get("article", {}).get("input_limit", 40) or 40)
    pool = pool[:input_limit]
    if not pool:
        print("✗ 无可用的新信号（可能全部被跨日去重排除）。用 --force 或换源。")
        return {**base, "exit_code": 1, "error": "all signals seen"}

    items = await build_items(pool)
    print(f"→ 进入工作流 {len(items)} 条信号（input_limit={input_limit}）")

    result = await run_article(
        items, cfg, settings, date, promp_dir(cfg), article_dir(cfg)
    )
    if result.get("error"):
        return {**base, "exit_code": result.get("exit_code", 1), "error": result["error"]}

    used_idx = [_parse_item_idx(uid) for uid in result.get("used_item_ids", [])]
    emitted = [pool[i] for i in used_idx if 0 <= i < len(pool)]
    new_fps = 0
    archived_fps = 0
    if emitted:
        new_fps, archived_fps = state.record_emitted(emitted, date)
        print(f"✓ 记录 {new_fps} 条信号指纹到 seen（跨日去重）")
        if archived_fps > 0:
            print(f"✓ 归档 {archived_fps} 条旧指纹到 .state/arch/")

    print(f"✓ 文章已产出: {result['files']['md']}")
    print(f"   HTML: {result['files']['html']}")
    print(f"   配图方案: {result['files']['plan']}")
    print(f"   门禁: {result['gate_action']} · 综合分: {result['overall_score']} · 修订: {result['revision']}")

    return {**base, "new_fingerprints": new_fps, **result}


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args()

    json_mode = args.json
    if json_mode:
        sys.stdout = sys.stderr

    try:
        cfg = load_config(args.config)
        if args.topics_only:
            result = asyncio.run(amain_topics_only(args, cfg))
        else:
            result = asyncio.run(amain(args, cfg))
    except KeyboardInterrupt:
        result = {"exit_code": 130, "error": "interrupted"}
    except Exception as e:  # noqa: BLE001
        result = {"exit_code": 1, "error": f"{type(e).__name__}: {e}"}

    if json_mode:
        sys.__stdout__.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif result.get("error"):
        print(f"✗ 运行失败: {result['error']}")

    sys.exit(int(result.get("exit_code", 1)))


if __name__ == "__main__":
    main()
