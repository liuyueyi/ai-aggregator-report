"""选题建议生成：读取已有日报 → LLM 生成选题 → 与前日差异对比 → Markdown 输出。"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from .llm import call_json, is_mock
from .renderer import date_path

SYSTEM = "你是选题策划专家，严格输出 JSON，不要解释。"


def _fallback_topics(
    tkey: str, tconf: dict, report_content: str, date: str
) -> dict:
    """mock/LLM 失败时的确定性兜底选题：基于日报内容提取前 3 个标题。"""
    titles = re.findall(r"#### \d+\.\s*\[(.+?)\]", report_content)
    suggestions = []
    for i, t in enumerate(titles[:3], 1):
        suggestions.append({
            "title": t[:30],
            "angle": f"基于 {tconf.get('name', tkey)} 热点「{t[:20]}」展开分析",
            "why_write": "该话题具有时效性和话题性，目标读者关注度高",
            "signals": [t],
            "format": "deep-dive",
            "priority": "high" if i == 1 else "medium",
            "read_time": "10min",
        })
    return {"suggestions": suggestions}


async def generate_topic_suggestions(
    topics: dict[str, dict],
    date: str,
    rdir: Path,
    settings: dict,
    prompts_dir: Path,
) -> dict[str, dict]:
    """为每个主题读取日报并生成选题建议。返回 {tkey: {topic_name, icon, suggestions[]}}。"""
    prompt_tpl = (prompts_dir / "article_topics.md").read_text(encoding="utf-8")
    llm_concurrency = int(settings.get("max_concurrency", 4))
    sem = asyncio.Semaphore(llm_concurrency)

    async def _gen_one(tkey: str, tconf: dict) -> tuple[str, dict | None]:
        async with sem:
            report_path = date_path(rdir, date) / f"{tkey}.md"
            if not report_path.exists():
                return tkey, None
            report_content = report_path.read_text(encoding="utf-8")
            if not report_content.strip():
                return tkey, None

            if is_mock(settings):
                result = _fallback_topics(tkey, tconf, report_content, date)
            else:
                user = prompt_tpl.replace("{{report_content}}", report_content)
                try:
                    result = await asyncio.to_thread(
                        call_json, SYSTEM, user, settings
                    )
                except Exception as err:
                    print(f"[topics:{tkey}] LLM failed, fallback: {err}")
                    result = _fallback_topics(tkey, tconf, report_content, date)

            if not isinstance(result, dict) or not result.get("suggestions"):
                result = _fallback_topics(tkey, tconf, report_content, date)
            return tkey, result

    results = await asyncio.gather(*[_gen_one(k, v) for k, v in topics.items()])

    out: dict[str, dict] = {}
    for tkey, result in results:
        if result is None:
            continue
        out[tkey] = {
            "topic_name": topics[tkey].get("name", tkey),
            "icon": topics[tkey].get("icon", ""),
            **result,
        }
        n = len(result.get("suggestions", []))
        print(f"✓ [{tkey}] {n} 条选题建议")
    return out


def _load_prev_suggestions(
    rdir: Path, date: str, topics: dict[str, dict] | None = None
) -> dict[str, list[dict]] | None:
    """从前一天的 topic_suggestions.md 解析选题标题，用于 diff 对比。
    若提供 topics，会用 topic key 作为返回的 key（否则用 Markdown 中的显示名）。"""
    from datetime import date as _date, timedelta

    d = _date.fromisoformat(date)
    prev = d - timedelta(days=1)
    prev_path = date_path(rdir, prev.isoformat()) / "topic_suggestions.md"
    if not prev_path.exists():
        return None
    try:
        content = prev_path.read_text(encoding="utf-8")
        parsed = _parse_topics_md(content)
        if topics:
            # 显示名 → topic key 反查
            name_to_key = {v.get("name", k): k for k, v in topics.items()}
            return {name_to_key.get(name, name): sugs for name, sugs in parsed.items()}
        return parsed
    except Exception:
        return None


def _parse_topics_md(content: str) -> dict[str, list[dict]]:
    """从 Markdown 中解析出 {topic_key: [{title}, ...]} 结构，仅用于 diff。"""
    result: dict[str, list[dict]] = {}
    current_topic = None
    for line in content.splitlines():
        # ## 🌍 综合早报
        m_topic = re.match(r"^##\s+\S+\s+(.+)$", line)
        if m_topic:
            current_topic = m_topic.group(1).strip()
            result.setdefault(current_topic, [])
            continue
        # ### 1. 具体标题
        m_title = re.match(r"^###\s+\d+\.\s+(.+)$", line)
        if m_title and current_topic is not None:
            result[current_topic].append({"title": m_title.group(1).strip()})
    return result


def _compute_diff(
    prev: dict[str, list[dict]] | None, curr: dict[str, list[dict]]
) -> dict[str, dict]:
    """对比前日与当日选题，逐主题输出 added/removed/changed。"""
    diff_out: dict[str, dict] = {}
    for tkey, curr_sugs in curr.items():
        prev_sugs = (prev or {}).get(tkey, [])
        prev_titles = {s["title"] for s in prev_sugs}
        curr_titles = {s["title"] for s in curr_sugs}
        added = curr_titles - prev_titles
        removed = prev_titles - curr_titles
        # changed: same title but angle 不同（从结构化数据比较）
        changed = set()
        prev_map = {s["title"]: s for s in prev_sugs}
        curr_map = {s["title"]: s for s in curr_sugs}
        for t in curr_titles & prev_titles:
            # MD-only prev 只有 title，无法比较 angle，视为不变
            if "angle" in prev_map[t] and curr_map[t].get("angle") != prev_map[t].get("angle"):
                changed.add(t)
        diff_out[tkey] = {
            "added": sorted(added),
            "removed": sorted(removed),
            "changed": sorted(changed),
        }
    return diff_out


def render_topics_md(
    date: str,
    suggestions: dict[str, dict],
    diff: dict[str, dict] | None = None,
) -> str:
    """将选题建议渲染为 Markdown 字符串。"""
    lines = [f"# 📋 选题建议 · {date}", ""]

    for tkey, data in suggestions.items():
        icon = data.get("icon", "")
        name = data.get("topic_name", tkey)
        sugs = data.get("suggestions", [])
        lines.append(f"## {icon} {name}")
        lines.append("")
        if not sugs:
            lines.append("（无选题建议）")
            lines.append("")
            continue
        for i, s in enumerate(sugs, 1):
            title = s.get("title", "")
            angle = s.get("angle", "")
            why_write = s.get("why_write", "")
            fmt = s.get("format", "")
            priority = s.get("priority", "")
            read_time = s.get("read_time", "")
            signals = s.get("signals", [])
            lines.append(f"### {i}. {title}")
            lines.append("")
            if why_write:
                lines.append(f"**💡 为什么值得写：**{why_write}")
                lines.append("")
            lines.append(f"> {angle}")
            lines.append("")
            meta_parts = []
            if fmt:
                meta_parts.append(f"**格式**: {fmt}")
            if priority:
                meta_parts.append(f"**优先级**: {priority}")
            if read_time:
                meta_parts.append(f"**阅读时间**: {read_time}")
            if meta_parts:
                lines.append(" · ".join(meta_parts))
                lines.append("")
            if signals:
                lines.append("**关联信号**:")
                for sig in signals:
                    lines.append(f"- {sig}")
                lines.append("")

    # 差异对比
    if diff:
        has_any_diff = any(
            d.get("added") or d.get("removed") or d.get("changed")
            for d in diff.values()
        )
        if has_any_diff:
            lines.append("---")
            lines.append("")
            lines.append("## 🔄 与前日对比")
            lines.append("")
            for tkey, d in diff.items():
                added = d.get("added", [])
                removed = d.get("removed", [])
                changed = d.get("changed", [])
                if not (added or removed or changed):
                    continue
                name = suggestions.get(tkey, {}).get("topic_name", tkey)
                icon = suggestions.get(tkey, {}).get("icon", "")
                lines.append(f"### {icon} {name}")
                lines.append("")
                if added:
                    lines.append("**新增:**")
                    for t in added:
                        lines.append(f"- ✅ {t}")
                    lines.append("")
                if removed:
                    lines.append("**移除:**")
                    for t in removed:
                        lines.append(f"- ❌ {t}")
                    lines.append("")
                if changed:
                    lines.append("**角度调整:**")
                    for t in changed:
                        lines.append(f"- 🔄 {t}")
                    lines.append("")

    return "\n".join(lines)
