from __future__ import annotations

import re

_ALLOWED = {"h1", "h2", "h3", "h4", "p", "blockquote", "ul", "ol", "li", "strong", "em", "a", "img", "code", "pre", "section", "br", "hr"}
_BAD_ATTR = re.compile(r"\s+(class|id|style|on\w+)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)


def build_markdown(title: str, plan: dict, draft_md: str, evidence: dict, date: str) -> str:
    """组装最终文章 Markdown：标题 + 摘要 + 证据链 + 正文 + 风险提示 + 来源。"""
    parts = [f"# {title}", ""]
    summary = (plan.get("summary") or "").strip()
    if summary:
        parts.append(f"> {summary}")
        parts.append("")
    parts.append(draft_md.strip())
    parts.append("")

    ev_items = evidence.get("items", [])
    if ev_items:
        parts.append("## 📎 证据链")
        parts.append("")
        for e in ev_items:
            parts.append(f"- {e.get('sourceType', '')} / {e.get('confidence', '')} | [{e.get('title', '')}]({e.get('url', '')})")
            if e.get("supports"):
                parts.append(f"  支撑：{'、'.join(e['supports'][:6])}")
        parts.append("")

    risks = [r for r in plan.get("riskNotes", []) if r.get("level") in ("medium", "high")]
    if risks:
        parts.append("## ⚠️ 风险与待核实")
        parts.append("")
        for r in risks:
            parts.append(f"- {r.get('issue', '')}（{r.get('handling', '')}）")
        parts.append("")

    parts.append("")
    return "\n".join(parts)


def markdown_to_wechat_html(md: str) -> str:
    """把 Markdown 转成微信兼容 HTML 子集（供 dry-run 预览排版）。"""
    try:
        import markdown as md_lib

        body = md_lib.markdown(md, extensions=["fenced_code", "sane_lists", "tables"])
    except Exception:  # noqa: BLE001
        body = _md_to_html_simple(md)
    body = _sanitize_html(body)
    return (
        '<section style="font-size:16px;line-height:1.8;color:#333;letter-spacing:0.5px;">'
        f"{body}</section>"
    )


def _sanitize_html(html: str) -> str:
    """微信清洗：移除 script/style/svg/iframe/div/span，剔除 class/id/on* 等属性，
    其余只保留白名单标签（保留 a 的 href、img 的 src）。"""
    html = re.sub(r"<(script|style|iframe|svg)\b[^>]*>.*?</\1\b[^>]*>", "", html, flags=re.I | re.S)
    html = re.sub(r"</?(?:div|span)\b[^>]*>", "", html, flags=re.I)
    html = _BAD_ATTR.sub("", html)
    html = re.sub(
        r"<(/?)(\w+)((?:\s[^<>]*)?)>",
        lambda m: m.group(0) if m.group(2).lower() in _ALLOWED else "",
        html,
    )
    return html


def _md_to_html_simple(md: str) -> str:
    """无 markdown 依赖时的轻量渲染（标题/列表/引用/加粗/链接/代码子集）。"""
    lines = []
    for raw in md.splitlines():
        line = raw
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            lvl = len(m.group(1))
            tag = "h2" if lvl <= 2 else "h3"
            lines.append(f"<{tag}>{m.group(2)}</{tag}>")
            continue
        m = re.match(r"^>\s?(.*)$", line)
        if m:
            lines.append(f"<blockquote>{_inline(m.group(1))}</blockquote>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", line)
        if m:
            lines.append(f"<li>{_inline(m.group(1))}</li>")
            continue
        if re.match(r"^\s*$", line):
            lines.append("<p></p>")
            continue
        lines.append(f"<p>{_inline(line)}</p>")
    return "\n".join(lines)


def _inline(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s