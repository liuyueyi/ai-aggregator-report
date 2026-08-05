from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .fetchers.base import Signal
from .llm import call_json, is_mock

SYSTEM = "你是资深中文媒体编辑，严格输出 JSON，不要解释。"

_AGE_TEXT = {
    "today": "今日",
    "past_72h": "近 3 天",
    "older": "多日前",
    "unknown": "时间未知",
    "today_window": "今日",
}


def _age_text(bucket: str) -> str:
    return _AGE_TEXT.get(bucket, "时间未知")


def _format_signal(s: Signal) -> dict:
    return {
        "source": s.source,
        "title": s.title,
        "url": s.url,
        "heat": s.heat,
        "score": round(s.score, 2),
        "raw_score": s.raw_score,
        "comments": s.comments,
        "author": s.author,
        "summary": s.summary,
        "content": s.content,
        "published_at": s.published_at,
        "age_bucket": s.age_bucket,
        "hn_url": s.hn_url,
        "gh_url": s.gh_url,
        "also_on": s.extra.get("also_on", []),
    }


def fallback_report(
    topic_cfg: dict,
    signals: list[Signal],
    date: str,
    reason: str = "模拟 LLM 模式（未接入真实 LLM）",
) -> dict:
    """LLM 不可用时的确定性兜底日报：以统一模板平铺原始信号，无 AI 深度分析。"""
    name = topic_cfg.get("name", "")
    icon = topic_cfg.get("icon", "")
    lines = [
        f"# {icon} {name} · {date}",
        "",
        f"> {reason}，以下为当日 {len(signals)} 条原始信号（未经 AI 深度分析）。",
        "",
    ]
    for i, s in enumerate(signals, 1):
        tm = s.published_at or _age_text(s.age_bucket)
        lines.append(f"#### {i}. [{s.title}]({s.url})")
        meta = f"- **来源**: {s.source} | **时间**: {tm}"
        if s.heat:
            meta += f" | **热度**: {s.heat}"
        lines.append(meta)
        links = []
        if s.hn_url:
            links.append(f"[讨论]({s.hn_url})")
        if s.gh_url:
            links.append(f"[GitHub]({s.gh_url})")
        if links:
            lines.append("- **链接**: " + " | ".join(links))
        lines.append(f"- **摘要**: {s.summary or '（无）'}")
        lines.append("")
    return {"markdown": "\n".join(lines), "tagline": f"{name} · {len(signals)} 条信号"}


async def generate_topic_report(
    topic_key: str,
    topic_cfg: dict,
    signals: list[Signal],
    date: str,
    recent_taglines: list[str],
    settings: dict,
    prompts_dir: Path,
) -> dict:
    """为一个主题生成日报 markdown + tagline。LLM 失败/为空时回落确定模板。"""
    if not signals:
        return {"markdown": None, "tagline": None}

    if is_mock(settings):
        return fallback_report(topic_cfg, signals, date, "模拟 LLM 模式（--mock-llm）")

    prompt_name = topic_cfg.get("prompt", "report.general.md")
    tpl = (prompts_dir / prompt_name).read_text(encoding="utf-8")
    tagline_block = "\n".join(f"- {t}" for t in recent_taglines) if recent_taglines else "（无历史记录）"

    user = (
        tpl.replace("{{date}}", date)
        .replace("{{topic_name}}", topic_cfg.get("name", ""))
        .replace("{{signals_json}}", json.dumps([_format_signal(s) for s in signals], ensure_ascii=False, indent=1))
        .replace("{{recent_taglines}}", tagline_block)
    )

    try:
        result = await asyncio.to_thread(call_json, SYSTEM, user, settings)
    except Exception as err:
        print(f"[report:{topic_key}] LLM failed, fallback: {err}")
        return fallback_report(topic_cfg, signals, date, "LLM 调用失败，输出原始信号")

    markdown: str = (result.get("markdown") or "").strip() if isinstance(result, dict) else ""
    if not markdown:
        return fallback_report(topic_cfg, signals, date, "LLM 输出为空，输出原始信号")
    tagline: str = (result.get("tagline") or "").strip() if isinstance(result, dict) else ""
    return {"markdown": markdown, "tagline": tagline}