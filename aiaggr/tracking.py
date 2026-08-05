from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .config import ROOT
from .fetchers.base import Signal
from .llm import call_json, is_mock
from .renderer import save_report

SYSTEM = "你是资深中文科技编辑，严格输出 JSON，不要解释。"

REPORTS = {
    "cli": {"report": "ai-cli", "title": "AI CLI / Claude Code Skills 生态"},
    "agents": {"report": "ai-agents", "title": "AI Agent 生态"},
}


def _sig(s: Signal) -> dict:
    return {
        "project": s.extra.get("project", s.source),
        "repo": s.extra.get("repo", s.gh_url),
        "kind": s.extra.get("kind", ""),
        "title": s.title,
        "url": s.url,
        "heat": s.heat,
        "score": round(s.score, 2),
        "comments": s.comments,
        "author": s.author,
        "published_at": s.published_at,
    }


def _fallback(kind: str, date: str, signals: list[Signal], reason: str) -> str:
    """确定性兜底：按项目分组平铺 Issues/PRs 与 Releases，不加 AI 深度分析。"""
    title = REPORTS[kind]["title"]
    lines = [f"# {title} · {date}", "", f"> {reason}，以下为当日追踪到社区动态（未经 AI 深度分析）。", ""]
    by_project: dict[str, list[Signal]] = {}
    for s in signals:
        by_project.setdefault(s.extra.get("project", s.source), []).append(s)
    for project in sorted(by_project):
        items = by_project[project]
        lines.append(f"## {project}")
        prs = [i for i in items if i.tags and i.tags[0] == "pr"]
        issues = [i for i in items if i.tags and i.tags[0] == "issue"]
        rels = [i for i in items if i.tags and i.tags[0] == "release"]
        lines.append(f"- PRs: {len(prs)} · Issues: {len(issues)} · Releases: {len(rels)}")
        for i in items:
            lines.append(f"- **{i.title}**  ({i.heat or '—'})  [{i.source}]({i.url})")
        lines.append("")
    return "\n".join(lines)


async def _generate(kind: str, signals: list[Signal], date: str,
                    settings: dict, prompts_dir: Path, rdir: Path) -> tuple[Path | None, int]:
    report_key = REPORTS[kind]["report"]
    tpl = (prompts_dir / f"tracking.{kind}.md").read_text(encoding="utf-8")
    user = (
        tpl.replace("{{date}}", date)
        .replace("{{signals_json}}", json.dumps([_sig(s) for s in signals], ensure_ascii=False, indent=1))
    )
    if is_mock(settings):
        md = _fallback(kind, date, signals, "模拟 LLM 模式（--mock-llm）")
    else:
        try:
            result = await asyncio.to_thread(call_json, SYSTEM, user, settings)
        except Exception as err:
            md = _fallback(kind, date, signals, f"LLM 调用失败，输出原始信号（{err}）")
        else:
            md = (result.get("markdown") or "").strip() if isinstance(result, dict) else ""
            if not md:
                md = _fallback(kind, date, signals, "LLM 输出为空，输出原始信号")
    path = save_report(md, report_key, date, rdir)
    print(f"✓ [{report_key}] 已保存到 {path.relative_to(ROOT) if path.exists() else path}")
    return path, len(signals)


async def generate_tracking_reports(
    tracking: dict[str, list[Signal]],
    settings: dict,
    date: str,
    prompts_dir: Path,
    rdir: Path,
) -> list[Path]:
    """为追踪信号生成 ai-cli.md / ai-agents.md 专题报告，返回已保存文件列表。"""
    saved: list[Path] = []
    for kind, report_key in (("cli", "cli_tracker"), ("agents", "agents_tracker")):
        signals = tracking.get(report_key, [])
        if not signals:
            continue
        path, _ = await _generate(kind, signals, date, settings, prompts_dir, rdir)
        if path:
            saved.append(path)
    return saved