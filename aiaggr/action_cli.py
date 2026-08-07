"""GitHub Actions 专用分段执行入口（分阶段管线 + artifact 中间产物）。

与 main.py 的差异：
- 同一份日报被拆成多个独立 job（fetch → aggregate → classify → deep → generate → suggest），
  阶段间用 GitHub Actions artifact 传递中间产物（signals / aggregated / pools），不落 git。
  提交/站点/飞书 由 workflow 的 commit job 统一完成。
- 设计约束（详见 .github/workflows/daily-report.yml 顶部注释）：
    1. 状态写入只收敛到 generate job（record_emitted + append_tagline）；其余 job 只读不改 .state。
    2. date 由 workflow input 固化，通过 --date 传入，全链路共享一个日期。
    3. 每个产物带 `__meta__`( schema + date + stage )，下游加载时校验；缺省/日期不符 => fail-fast，指引重跑上游。

stage 链：
    fetch      → signals.json   （抓取全部源）
    aggregate  → aggregated.json （同日去重 + 跨日 mark_seen 只读标记）
    classify   → pools.json      （规则 + LLM 精修，归类到各主题）     stage=classify
    deep       → pools.json      （可选：为各主题 top-N 拉正文）       stage=deep
    generate   → report/*.md + .state（唯一写状态点；生态追踪专题也在此并发生成）
    suggest    → topic_suggestions.md（读当日日报，生成选题建议）

用法：
    python -m aiaggr.action_cli --job <job> --date YYYY-MM-DD [--workdir <dir>] [--topic a,b] [--mock-llm] [--source a,b]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import (
    ROOT,
    enabled_topics,
    llm_settings,
    load_config,
    promp_dir,
    report_dir,
    state_dir,
)
from .classifier import classify
from .dedup import aggregate
from .deep import enrich_with_content
from .fetchers import select_fetchers
from .fetchers.base import Signal
from .main import fetch_all
from .pipeline import generate_topic_report
from .renderer import date_path, save_index, save_report
from .state import StateStore

SCHEMA = 1
TRACKING_KEYS = ("cli_tracker", "agents_tracker")


# ---------------------------------------------------------------- serialization

def _sig_to_dict(s: Signal) -> dict:
    return s.to_dict()


def _sig_from_dict(d: dict) -> Signal:
    return Signal(**d)


def _write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _load(path: Path, expected_date: str, stage: str) -> dict:
    """读取产物并校验 __meta__ 的 schema/date/stage。失败交给调用方捕获。"""
    if not path.exists():
        raise FileNotFoundError(f"缺少上游产物 {path}，请重跑其上游 job。")
    data = json.loads(path.read_text(encoding="utf-8"))
    m = data.get("__meta__") or {}
    if m.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema={m.get('schema')} != {SCHEMA}，请整体重跑。")
    if m.get("date") != expected_date:
        raise ValueError(f"{path}: 日期={m.get('date')} != 目标 {expected_date}，请重跑上游 job。")
    if m.get("stage") != stage:
        raise ValueError(f"{path}: stage={m.get('stage')}，预期来自 {stage}。")
    return data


def _write_signals(path: Path, signals: list[Signal], date: str, stage: str) -> None:
    _write(path, {
        "__meta__": {"schema": SCHEMA, "date": date, "stage": stage},
        "signals": [_sig_to_dict(s) for s in signals],
    })


def _write_tracking(path: Path, tracking: dict[str, list[Signal]]) -> None:
    _write(path, {"signals": {k: [_sig_to_dict(s) for s in v] for k, v in tracking.items()}})


def _read_tracking(path: Path) -> dict[str, list[Signal]]:
    if not path.exists():
        return {}
    return {k: [_sig_from_dict(d) for d in v]
            for k, v in json.loads(path.read_text(encoding="utf-8")).get("signals", {}).items()}


def _write_pools(path: Path, pools: dict[str, list[Signal]], tracking: dict[str, list[Signal]],
                 date: str, stage: str) -> None:
    _write(path, {
        "__meta__": {"schema": SCHEMA, "date": date, "stage": stage},
        "pools": {k: [_sig_to_dict(s) for s in v] for k, v in pools.items()},
        "tracking": {k: [_sig_to_dict(s) for s in v] for k, v in tracking.items()},
    })


def _read_pools(path: Path, date: str) -> tuple[dict[str, list[Signal]], dict[str, list[Signal]]]:
    """读取 pools.json；deep 与 generate 都接受（stage ∈ classify/deep）。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    m = data.get("__meta__") or {}
    if m.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema={m.get('schema')} != {SCHEMA}，请整体重跑。")
    if m.get("date") != date:
        raise ValueError(f"{path}: 日期={m.get('date')} != 目标 {date}，请重跑上游 job。")
    if m.get("stage") not in ("classify", "deep"):
        raise ValueError(f"{path}: stage={m.get('stage')}，预期 classify 或 deep。")
    pools = {k: [_sig_from_dict(d) for d in v] for k, v in data.get("pools", {}).items()}
    tracking = {k: [_sig_from_dict(d) for d in v] for k, v in data.get("tracking", {}).items()}
    return pools, tracking


# ---------------------------------------------------------------- helpers

def _settings(cfg, args) -> dict:
    s = llm_settings(cfg)
    if args.mock_llm:
        s["mock"] = True
    return s


def _resolve_topics(cfg, args) -> dict:
    topics = enabled_topics(cfg)
    if getattr(args, "topic", None):
        keys = [t.strip() for t in args.topic.split(",") if t.strip()]
        topics = {k: v for k, v in topics.items() if k in keys}
    return topics


def _state(cfg, date) -> StateStore:
    return StateStore(state_dir(cfg), window_days=int(cfg.get("dedup", {}).get("window_days", 7)))


def _sep(signals: list[Signal]) -> tuple[list[Signal], dict[str, list[Signal]]]:
    """划出生态追踪信号（不参与主题日报分类）。返回 (normal_signals, tracking)。"""
    tracking: dict[str, list[Signal]] = {}
    normal: list[Signal] = []
    for s in signals:
        if s.source_key in TRACKING_KEYS:
            tracking.setdefault(s.source_key, []).append(s)
        else:
            normal.append(s)
    return normal, tracking


# ---------------------------------------------------------------- 日志/计时

_JOB_NAMES = {
    "fetch": "① 数据抓取",
    "aggregate": "② 同日去重 + 跨日标记",
    "classify": "③ 主题分类",
    "deep": "④ 正文增强（deep）",
    "generate": "⑤ 主题日报生成（含生态追踪）",
    "suggest": "⑥ 选题建议",
    "site": "⑦ 站点产物重建",
    "notify": "⑧ 飞书推送",
}


def _banner(job: str, date: str, settings: dict) -> None:
    """job 入口引导日志：job 名、日期、LLM 状态。"""
    print("=" * 56)
    print(f"▶ {_JOB_NAMES.get(job, job)} · 报告日期 {date}")
    print("=" * 56)
    if settings.get("mock"):
        print("→ LLM: 未启用（mock 模式，不调用模型）")
    elif settings.get("api_key"):
        mode = settings.get("model") or "(未配置 LLM_MODEL)"
        base = settings.get("base_url") or "(未配置 LLM_BASE_URL)"
        print(f"→ LLM: 已启用 · 模型: {mode} · 接口: {base}")
    else:
        print("→ LLM: 未配置 LLM_API_KEY（将按规则/兜底路径运行）")


class _Stage:
    """job 内部子阶段计时：start/end 打印，结束汇总。"""

    def __init__(self) -> None:
        self._t0: dict[str, float] = {}
        self._dur: dict[str, float] = {}
        self._global = time.perf_counter()

    def start(self, name: str) -> None:
        self._t0[name] = time.perf_counter()
        print(f"→ 阶段开始: {name}")

    def end(self, name: str, extra: str = "") -> float:
        sec = time.perf_counter() - self._t0.pop(name, time.perf_counter())
        self._dur[name] = sec
        print(f"✓ 阶段结束: {name} · 耗时 {_fmt_duration(sec)}{extra}")
        return sec

    def summary(self) -> None:
        if not self._dur:
            return
        print("== 本 job 耗时汇总 ==")
        rows = sorted(self._dur.items(), key=lambda kv: kv[1], reverse=True)
        rows.append(("job 总计", time.perf_counter() - self._global))
        for name, sec in rows:
            print(f"  - {name}: {_fmt_duration(sec)}")


def _fmt_duration(sec: float) -> str:
    if sec < 0.001:
        return f"{sec * 1000:.1f} ms"
    if sec < 60:
        return f"{sec:.2f} 秒"
    return f"{sec / 60:.1f} 分钟"


# ---------------------------------------------------------------- jobs

def job_fetch(cfg, args, settings) -> dict:
    """① 抓取。"""
    date = args.date
    st = _Stage()
    st.start("数据抓取")
    requested = [s.strip() for s in args.source.split(",") if s.strip()] if args.source else None
    fetchers = select_fetchers(cfg, requested)
    if not fetchers:
        raise SystemExit("未选中任何数据源（检查 --source / config enabled）")
    if args.limit:
        for f in fetchers.values():
            f.config["limit"] = args.limit
    print(f"→ 并行抓取 {len(fetchers)} 个数据源 ...")
    signals, sources_empty = asyncio.run(fetch_all(fetchers))
    if not signals:
        st.end("数据抓取", extra="（空结果）")
        raise SystemExit("no signals fetched")
    st.end("数据抓取", extra=f"（{len(signals)} 条原始信号）")
    _, tracking = _sep(signals)
    st.start("写 fetch 产物")
    _write_signals(Path(args.work_dir) / "signals.json", signals, date, "fetch")
    st.end("写 fetch 产物")
    tr = {k: len(v) for k, v in tracking.items() if v}
    if tr:
        print(f"✓ 生态追踪信号：{tr}")
    if sources_empty:
        print(f"→ 空结果/失败源: {sources_empty}")
    st.summary()
    return {"exit_code": 0, "signals": len(signals), "sources": len(fetchers), "sources_empty": sources_empty}


def job_aggregate(cfg, args, settings) -> dict:
    """② 聚合去重 + 跨日 mark_seen（只读，不写 .state）。"""
    date = args.date
    st = _Stage()
    st.start("同日去重与聚合")
    src_path = Path(args.work_dir) / "signals.json"
    _load(src_path, date, "fetch")
    signals = [_sig_from_dict(d) for d in json.loads(src_path.read_text(encoding="utf-8"))["signals"]]
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    aggregated = aggregate(signals, today=date_obj,
                           ignore_tracking=cfg.get("dedup", {}).get("ignore_tracking", True))
    st.end("同日去重与聚合", extra=f"（{len(aggregated)}/{len(signals)}）")
    st.start("跨日去重")
    aggregated = _state(cfg, date).mark_seen(aggregated, date)
    n_seen = sum(1 for s in aggregated if s.seen_on)
    st.end("跨日去重", extra=f"（命中已有指纹 {n_seen} 条）")
    normal, tracking = _sep(aggregated)
    st.start("写 aggregated 产物")
    _write_signals(Path(args.work_dir) / "aggregated.json", normal, date, "aggregate")
    _write_tracking(Path(args.work_dir) / "tracking.json", tracking)
    st.end("写 aggregated 产物")
    tr = {k: len(v) for k, v in tracking.items() if v}
    if tr:
        print(f"✓ 生态追踪信号：{tr}")
    st.summary()
    return {"exit_code": 0, "unique": len(normal), "seen": n_seen, "tracking": tr}


def job_classify(cfg, args, settings) -> dict:
    """③ 主题分类。"""
    date = args.date
    st = _Stage()
    st.start("主题分类")
    src_path = Path(args.work_dir) / "aggregated.json"
    _load(src_path, date, "aggregate")
    signals = [_sig_from_dict(d) for d in json.loads(src_path.read_text(encoding="utf-8"))["signals"]]
    topics = _resolve_topics(cfg, args)
    use_llm = not args.no_llm and not settings.get("mock")
    pools = classify(signals, topics, settings, use_llm=use_llm)
    st.end("主题分类", extra=f"（{'' if use_llm else '规则-only，'}共 {len(signals)} 条信号）")
    counts = {k: len(v) for k, v in pools.items()}
    print(f"✓ 分类结果（含 LLM 精修：{use_llm}）: {counts}")
    st.start("写 classify 产物")
    tracking = _read_tracking(Path(args.work_dir) / "tracking.json")
    _write_pools(Path(args.work_dir) / "pools.json", pools, tracking, date, "classify")
    st.end("写 classify 产物")
    st.summary()
    return {"exit_code": 0, "llm_refined": use_llm, "topic_counts": counts}


def _deep_picks(cfg, pools: dict[str, list[Signal]], date: str,
                topics: dict[str, dict]) -> list[Signal]:
    cross_day_exclude = cfg.get("dedup", {}).get("cross_day_exclude", True)
    picks: list[Signal] = []
    seen: set[int] = set()
    for tkey, tconf in topics.items():
        pool = pools.get(tkey, [])
        if cross_day_exclude:
            pool = [p for p in pool if not p.seen_on]
        for s in sorted(pool, key=lambda x: x.score, reverse=True)[: int(tconf.get("limit", 15))]:
            if id(s) not in seen:
                seen.add(id(s))
                picks.append(s)
    return picks


async def job_deep_async(cfg, args, settings) -> dict:
    """④ 正文增强：对主题 pool 的 top-N 信号拉正文。"""
    date = args.date
    st = _Stage()
    st.start("正文增强")
    src_path = Path(args.work_dir) / "pools.json"
    _load(src_path, date, "classify")
    pools, tracking = _read_pools(src_path, date)
    picks = _deep_picks(cfg, pools, date, _resolve_topics(cfg, args))
    if picks:
        print(f"→ deep: 正文抓取 {len(picks)} 条信号（并发） ...")
        await enrich_with_content(picks)
    st.end("正文增强", extra=f"（{len(picks)} 条拉正文）")
    st.start("写 deep 产物")
    _write_pools(src_path, pools, tracking, date, "deep")
    st.end("写 deep 产物")
    st.summary()
    return {"exit_code": 0, "deep_picked": len(picks)}


def job_generate(cfg, args, settings) -> dict:
    """⑤ 主题日报生成（唯一写状态点）。"""
    date = args.date
    st = _Stage()
    src_path = Path(args.work_dir) / "pools.json"
    if not src_path.exists():
        raise SystemExit(f"缺少 {src_path}，请先重跑 classify（或 deep）job。")
    pools, tracking = _read_pools(src_path, date)
    topics = _resolve_topics(cfg, args)
    rdir = report_dir(cfg)
    state = _state(cfg, date)
    cross_day_exclude = cfg.get("dedup", {}).get("cross_day_exclude", True)
    tagline_map = state.taglines_by_topic(days=int(cfg.get("dedup", {}).get("window_days", 7)))
    prompts = promp_dir(cfg)
    llm_concurrency = int(settings.get("max_concurrency", 4))
    sem = asyncio.Semaphore(llm_concurrency)

    st.start("主题日报生成")
    print(f"→ 并发生成 {len(topics)} 份主题日报（LLM 并发上限 {llm_concurrency}，跨日去重排除：{cross_day_exclude}）...")

    async def _gen_one(tkey: str) -> tuple[str, list[Signal], dict | None]:
        async with sem:
            tconf = topics[tkey]
            pool = pools.get(tkey, [])
            if cross_day_exclude:
                pool = [p for p in pool if not p.seen_on]
            if not pool:
                return tkey, [], None
            limit = int(tconf.get("limit", 15))
            pool_sorted = sorted(pool, key=lambda s: s.score, reverse=True)[:limit]
            result = await generate_topic_report(
                tkey, tconf, pool_sorted, date, tagline_map.get(tkey, []), settings, prompts
            )
            return tkey, pool_sorted, result

    async def _run_all():
        return await asyncio.gather(*[_gen_one(t) for t in topics])

    results = asyncio.run(_run_all())
    saved_files: list[Path] = []
    entries: list[dict] = []
    emitted: list[Signal] = []

    for tkey, pool_sorted, result in results:
        tconf = topics[tkey]
        if result is None or not result.get("markdown"):
            entries.append({"key": tkey, "name": tconf.get("name", tkey),
                            "icon": tconf.get("icon", ""), "tagline": "（无信号）" if not pool_sorted else "（生成失败）",
                            "file": f"{date}/{tkey}", "count": len(pool_sorted), "skipped": True})
            continue
        path = save_report(result["markdown"], tkey, date, rdir)
        saved_files.append(path)
        entries.append({"key": tkey, "name": tconf.get("name", tkey),
                        "icon": tconf.get("icon", ""),
                        "tagline": result.get("tagline", ""),
                        "file": f"{date}/{tkey}", "count": len(pool_sorted), "skipped": False})
        state.append_tagline(date, tkey, result.get("tagline", ""))
        emitted.extend(pool_sorted)

    # 生态追踪专题报告（ai-cli / ai-agents），同批并发生成，仅落盘、不写 .state 指纹
    tracking = _read_tracking(Path(args.work_dir) / "tracking.json")
    if tracking:
        from .tracking import generate_tracking_reports
        saved_files.extend(asyncio.run(generate_tracking_reports(
            tracking, settings, date, prompts, rdir, sem=sem)))

    st.end("主题日报生成", extra=f"（{len(saved_files)} 份产物）")

    if not saved_files:
        raise SystemExit("all reports failed")

    st.start("落盘与状态更新")
    new_fps, archived_fps = state.record_emitted(emitted, date)
    print(f"✓ 记录 {new_fps} 条新指纹到 seen · 归档 {archived_fps} 条（跨日去重）")
    save_index(date, entries, rdir)
    print(f"✓ 当日索引已保存 → {date_path(rdir, date) / 'index.md'}")
    st.end("落盘与状态更新")
    # 供 commit job 构造飞书卡片与 summary（entries 含 key/name/tagline）
    st.start("写 entries 产物")
    _write(Path(args.work_dir) / "entries.json",
           {"__meta__": {"schema": SCHEMA, "date": date, "stage": "generate"}, "entries": entries})
    st.end("写 entries 产物")
    st.summary()
    return {"exit_code": 0, "saved": len(saved_files), "new_fingerprints": new_fps,
            "archived": archived_fps, "topics": len(entries)}


async def job_suggest_async(cfg, args, settings) -> dict:
    """⑥ 选题建议：读当日日报 md → 生成 topic_suggestions.md（含前日 diff）。"""
    from .topics import _compute_diff, _load_prev_suggestions, generate_topic_suggestions, render_topics_md

    date = args.date
    st = _Stage()
    rdir = report_dir(cfg)
    topics = {k: v for k, v in _resolve_topics(cfg, args).items()
              if (date_path(rdir, date) / f"{k}.md").exists()}
    prompts = promp_dir(cfg)
    st.start("选题建议生成")
    if not topics:
        print("→ 无可用主题日报，跳过选题建议")
        suggestions: dict = {}
    else:
        print(f"→ 为 {len(topics)} 个主题生成选题建议 ...")
        suggestions = await generate_topic_suggestions(topics, date, rdir, settings, prompts)
    # 无论是否生成到内容，都写 topic_suggestions.md，保证 artifact 稳定存在（commit 依赖它）
    prev = _load_prev_suggestions(rdir, date, topics) if topics else None
    curr = {k: v.get("suggestions", []) for k, v in suggestions.items()}
    diff = _compute_diff(prev, curr)
    md = render_topics_md(date, suggestions, diff)
    ts = date_path(rdir, date) / "topic_suggestions.md"
    ts.write_text(md, encoding="utf-8")
    print(f"✓ 选题建议已保存: {ts.relative_to(ROOT)}（{len(suggestions)} 个主题，含前日 diff：{len(diff)}）")
    st.end("选题建议生成")
    st.summary()
    return {"exit_code": 0, "topics": len(suggestions)}


# ---------------------------------------------------------------- CLI

def job_site(cfg, args, settings) -> dict:
    """⑦ 重建站点产物（manifest.json + feed.xml）到 site/。"""
    from .config import site_dir
    from .site import build_site

    st = _Stage()
    st.start("站点产物重建")
    rdir = report_dir(cfg)
    state = _state(cfg, args.date)
    w = int(cfg.get("dedup", {}).get("window_days", 7))
    tagline_map: dict[str, dict[str, str]] = {}
    for r in state.load_taglines(days=w):
        d, t, tl = r.get("date"), r.get("topic"), r.get("tagline", "")
        if d and t and tl:
            tagline_map.setdefault(d, {})[t] = tl
    base_url = os.environ.get("PAGES_URL") or cfg.get("site", {}).get("base_url", "") or ""
    build_site(rdir, site_dir(cfg), base_url, enabled_topics(cfg), tagline_map)
    st.end("站点产物重建")
    st.summary()
    return {"exit_code": 0, "site": str(site_dir(cfg).relative_to(ROOT))}


async def job_notify_async(cfg, args, settings) -> dict:
    """⑧ 飞书推送（读 entries.json 构造卡片）。无配置静默跳过。"""
    from .notify import build_feishu_card, send_feishu

    st = _Stage()
    st.start("飞书推送")
    ep = Path(args.work_dir) / "entries.json"
    entries: list[dict] = []
    if ep.exists():
        try:
            entries = json.loads(ep.read_text(encoding="utf-8")).get("entries", [])
        except Exception:
            entries = []
    if not entries:
        st.end("飞书推送", extra="（无主题条目，跳过）")
        return {"exit_code": 0, "notified": False}
    title, content = build_feishu_card(args.date, entries)
    ok = await send_feishu(title, content)
    st.end("飞书推送")
    st.summary()
    return {"exit_code": 0, "notified": ok}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aiaggr.action")
    p.add_argument("--job", required=True,
                   choices=["fetch", "aggregate", "classify", "deep", "generate", "suggest", "site", "notify"])
    p.add_argument("--date", required=True, help="报告日期 YYYY-MM-DD（workflow input 固化，跨 job 一致）")
    p.add_argument("--work-dir", dest="work_dir", default=".action_work", help="中间产物目录")
    p.add_argument("--topic", help="只看指定主题（逗号分隔，默认全部）")
    p.add_argument("--source", help="数据源 key（逗号分隔；仅 fetch 用）")
    p.add_argument("--limit", type=int, help="抓取条数上限")
    p.add_argument("--no-llm", action="store_true", help="跳过 LLM（classify 用）")
    p.add_argument("--mock-llm", action="store_true", help="mock LLM 模式")
    p.add_argument("--config", help="config.yaml 路径")
    return p


def main() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    args = build_parser().parse_args()
    cfg = load_config(args.config)
    settings = _settings(cfg, args)
    _banner(args.job, args.date, settings)
    try:
        if args.job == "fetch":
            result = job_fetch(cfg, args, settings)
        elif args.job == "aggregate":
            result = job_aggregate(cfg, args, settings)
        elif args.job == "classify":
            result = job_classify(cfg, args, settings)
        elif args.job == "deep":
            result = asyncio.run(job_deep_async(cfg, args, settings))
        elif args.job == "generate":
            result = job_generate(cfg, args, settings)
        elif args.job == "suggest":
            result = asyncio.run(job_suggest_async(cfg, args, settings))
        elif args.job == "site":
            result = job_site(cfg, args, settings)
        elif args.job == "notify":
            result = asyncio.run(job_notify_async(cfg, args, settings))
        else:
            raise SystemExit(f"unknown job: {args.job}")
    except SystemExit as e:
        print(f"✗ job({args.job}): {e}")
        sys.exit(2)
    except FileNotFoundError as e:
        print(f"✗ job({args.job}) 缺少上游产物: {e}")
        sys.exit(2)
    except ValueError as e:
        print(f"✗ job({args.job}) 产物校验失败: {e}")
        sys.exit(2)
    except Exception as e:  # noqa: BLE001
        print(f"✗ job({args.job}) 失败: {type(e).__name__}: {e}")
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()