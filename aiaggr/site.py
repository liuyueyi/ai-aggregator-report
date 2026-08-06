from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path

# 站点产物：manifest.json（Web UI 数据）+ feed.xml（RSS 2.0 订阅）
# 写入 site/ 目录（可配 config.site.dir），由 GitHub Pages / 任意静态托管服务。

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_FEED_ITEMS = 30
_SPECIAL_FILES = {"topic_suggestions"}  # 非主题的特殊 md 文件：纳入 reports（Web 选题入口）但不注册为主题

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def to_rfc822(d: dt.date) -> str:
    return (
        f"{_DAYS[d.weekday()]}, {d.day:02d} {_MONTHS[d.month - 1]} {d.year} "
        "00:00:00 +0800"
    )


def escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def scan_dates(report_dir: Path) -> list[dict]:
    """扫描 report/YYYY/MM/DD/ 下所有日报，返回升序的 [{date, reports:[topic...]}]。"""
    entries: list[dict] = []
    if not report_dir.is_dir():
        return entries
    for y in sorted(report_dir.iterdir()):
        if not y.is_dir() or not y.name.isdigit():
            continue
        for m in sorted(y.iterdir()):
            if not m.is_dir() or not m.name.isdigit():
                continue
            for d in sorted(m.iterdir()):
                if not d.is_dir() or not d.name.isdigit():
                    continue
                date = f"{y.name}-{m.name}-{d.name}"
                if not DATE_RE.match(date):
                    continue
                reports = sorted(p.stem for p in d.glob("*.md") if p.stem != "index")
                if reports:
                    entries.append({"date": date, "reports": reports})
    return entries


def _md_to_html_simple(text: str) -> str:
    """轻量 markdown→HTML：覆盖本项目的报告子集（标题/引用/列表/加粗/链接/代码）。
    仅在 markdown 库不可用时作为兜底，保证 feed 全文在无网环境也能生成。"""
    lines = text.splitlines()
    out: list[str] = []
    para: list[str] = []

    def flush_para():
        if para:
            out.append(f"<p>{' '.join(para)}</p>")
            para.clear()

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        return s

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush_para()
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue
        if line.startswith("> "):
            flush_para()
            out.append(f"<blockquote><p>{inline(line[2:])}</p></blockquote>")
            i += 1
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_para()
            items = []
            bullet = re.compile(r"^\s*[-*]\s+")
            while i < len(lines) and bullet.match(lines[i]):
                m = bullet.match(lines[i])
                items.append(f"<li>{inline(lines[i][m.end():])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            flush_para()
            items = []
            num = re.compile(r"^\s*\d+\.\s+")
            while i < len(lines) and num.match(lines[i]):
                m = num.match(lines[i])
                items.append(f"<li>{inline(lines[i][m.end():])}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        if re.match(r"^[-=]{3,}$", line.strip()):
            flush_para()
            out.append("<hr/>")
            i += 1
            continue
        para.append(inline(line))
        i += 1
    flush_para()
    return "\n".join(out)


def render_md_to_html(text: str) -> str:
    """markdown → HTML。优先用完整 markdown 库，不可用时降级到内置轻量转换器。"""
    try:
        import markdown as _md

        return _md.markdown(text, extensions=["extra", "tables", "fenced_code"])
    except ImportError:
        return _md_to_html_simple(text)


def _report_names(topics_cfg: dict) -> dict[str, str]:
    return {k: (v.get("name") or k) for k, v in topics_cfg.items()}


def build_manifest(
    report_dir: Path,
    root: Path,
    topics_cfg: dict,
    tagline_map: dict[str, dict[str, str]] | None = None,
) -> None:
    """生成 manifest.json：{generated, topics, dates}，新日期在前。

    - topics: {key: {name, icon}} 全量主题元信息（含追踪专题 ai-cli/ai-agents）
    - dates:  [{date, reports:[{key, tagline}]}]，tagline 取自 .state/taglines.jsonl
    """
    entries = scan_dates(report_dir)

    # 主题元信息：优先用 config 的 name/icon，未在 config 的（追踪专题）给兜底
    topics_meta: dict[str, dict] = {}
    for k, v in (topics_cfg or {}).items():
        topics_meta[k] = {"name": v.get("name", k), "icon": v.get("icon", "")}
    for e in entries:
        for rep in e["reports"]:
            if rep not in topics_meta and rep not in _SPECIAL_FILES:
                topics_meta[rep] = {"name": rep, "icon": ""}

    tl = tagline_map or {}
    for e in entries:
        day_tl = tl.get(e["date"], {}) or {}
        e["reports"] = [
            {"key": rep, "tagline": day_tl.get(rep, "")}
            for rep in e["reports"]
        ]

    manifest = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "topics": topics_meta,
        "dates": list(reversed(entries)),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"→ manifest.json 更新：{len(entries)} 天 · {len(topics_meta)} 主题")


def build_feed(report_dir: Path, root: Path, base_url: str, topics_cfg: dict) -> None:
    """生成 feed.xml（RSS 2.0，含全文 content:encoded，最新 {MAX_FEED_ITEMS} 条）。"""
    names = _report_names(topics_cfg)
    base = base_url.rstrip("/")
    entries = list(reversed(scan_dates(report_dir)))

    feed_items: list[tuple[str, str]] = []
    for e in entries:
        for report in e["reports"]:
            feed_items.append((e["date"], report))
            if len(feed_items) >= MAX_FEED_ITEMS:
                break
        if len(feed_items) >= MAX_FEED_ITEMS:
            break

    items: list[str] = []
    for date, report in feed_items:
        label = names.get(report, report)
        title = f"{label} · {date}"
        link = f"{base}/#{date}/{report}" if base else f"#{date}/{report}"
        y, m, d = (int(x) for x in date.split("-"))
        pub_date = to_rfc822(dt.date(y, m, d))
        md_path = report_dir / y.__str__().zfill(4) / m.__str__().zfill(2) / d.__str__().zfill(2) / f"{report}.md"
        try:
            raw = md_path.read_text(encoding="utf-8")
            html = render_md_to_html(raw)
            text = re.sub(r"<[^>]+>", "", html)
            text = re.sub(r"\s+", " ", text).strip()
            summary = text[:500] + "..." if len(text) > 500 else text
            safe_html = html.replace("]]>", "]]]]><![CDATA[")
        except OSError:
            summary = escape_xml(title)
            safe_html = escape_xml(title)
        items.append(
            "    <item>\n"
            f"      <title>{escape_xml(title)}</title>\n"
            f"      <link>{escape_xml(link)}</link>\n"
            f"      <guid isPermaLink=\"true\">{escape_xml(link)}</guid>\n"
            f"      <pubDate>{pub_date}</pubDate>\n"
            f"      <description>{escape_xml(summary)}</description>\n"
            f"      <content:encoded><![CDATA[{safe_html}]]></content:encoded>\n"
            "    </item>"
        )

    now = dt.datetime.now(dt.timezone.utc)
    feed = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/">\n'
        "  <channel>\n"
        "    <title>AI 聚合日报 · ai-aggregator-report</title>\n"
        f"    <link>{escape_xml(base) if base else ''}</link>\n"
        "    <description>多源热点采集 · 每日多主题日报 · Daily AI news digest</description>\n"
        "    <language>zh-CN</language>\n"
        f"    <atom:link href=\"{escape_xml(base)}/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>\n"
        f"    <lastBuildDate>{to_rfc822(now.date())}</lastBuildDate>\n"
        + "\n".join(items)
        + "\n  </channel>\n</rss>\n"
    )
    (root / "feed.xml").write_text(feed, encoding="utf-8")
    print(f"→ feed.xml 更新：{len(feed_items)} 条")


def build_site(
    report_dir: Path,
    root: Path,
    base_url: str,
    topics_cfg: dict,
    tagline_map: dict[str, dict[str, str]] | None = None,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    build_manifest(report_dir, root, topics_cfg, tagline_map)
    build_feed(report_dir, root, base_url, topics_cfg)
