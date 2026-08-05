from __future__ import annotations

from pathlib import Path


def report_exists(topic_key: str, date: str, root: Path) -> bool:
    return (date_path(root, date) / f"{topic_key}.md").exists()


def date_path(root: Path, date: str) -> Path:
    year, month, day = date.split("-")
    return root / year / month / day


def save_report(markdown: str, topic_key: str, date: str, root: Path) -> Path:
    """保存到 report/YYYY/MM/DD/{topic_key}.md。"""
    d = date_path(root, date)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{topic_key}.md"
    p.write_text(markdown, encoding="utf-8")
    return p


def save_index(date: str, entries: list[dict], root: Path) -> Path:
    """生成当日 index.md：汇总各主题日报入口 + tagline。"""
    d = date_path(root, date)
    d.mkdir(parents=True, exist_ok=True)
    lines = [f"# AI 聚合日报 · {date}", "", "> 当日按主题生成的各份日报。", ""]
    for e in entries:
        name = e.get("name", e.get("topic", ""))
        icon = e.get("icon", "")
        tagline = e.get("tagline", "")
        lines.append(f"- [{icon} {name}]({e.get('file', '')}.md){f' — {tagline}' if tagline else ''}")
    lines.append("")
    p = d / "index.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p