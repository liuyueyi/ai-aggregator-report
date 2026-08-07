from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup

from .base import BaseFetcher, Signal, normalize_score

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"
_DAILYDAWN_URL = "https://dailydawn.dev/zh.json"

# DailyDawn 是一份「完整的综合日报」，单篇正文约 20-30KB。
# summary 仅保留开头速览（足够长以覆盖各小节标题与导语），
# 完整正文存于 content，并按 h2/h3 拆分为 sections 供下游做子主题综合分析。
_SUMMARY_CAP = 2000
_SECTION_TAGS = ("h1", "h2", "h3", "h4")


def _parse_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text("\n", strip=True)


def _split_sections(html: str) -> list[dict]:
    """按标题标签把一篇综合日报拆成 {heading, text} 小节，供子主题分析。"""
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    sections: list[dict] = []
    cur: dict = {"heading": "", "text": ""}
    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"]):
        if el.name in _SECTION_TAGS:
            if cur["text"].strip() or cur["heading"]:
                sections.append(cur)
            cur = {"heading": el.get_text(strip=True), "text": ""}
        else:
            piece = el.get_text(" ", strip=True).strip()
            if piece:
                cur["text"] += piece + "\n"
    if cur["text"].strip() or cur["heading"]:
        sections.append(cur)
    return [s for s in sections if s["text"].strip()]


class DailyDawnFetcher(BaseFetcher):
    """DailyDawn 每日黎明 AI 趋势日报抓取器。

    从 https://dailydawn.dev/zh.json 获取 JSON Feed 格式的 AI 趋势信号。
    每日更新，每份都是一篇完整的综合日报（含多个小节）。
    抓取全量正文：summary 保留速览，content 存全文纯文本，
    extra.sections 存按小节拆分的结构，便于下游做子主题综合分析。
    """

    source_key = "dailydawn"
    source_name = "DailyDawn"
    timeout = 20.0

    def __init__(self, config: dict | None = None):
        super().__init__(config)

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        limit = self.config.get("limit", 10)
        hours = int(self.config.get("hours", 48) or 48)

        try:
            resp = await client.get(
                _DAILYDAWN_URL,
                headers={"User-Agent": _UA},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[{self.source_name}] fetch failed: {type(e).__name__}: {e}")
            return []

        items = data.get("items", [])
        if not items:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        signals: list[Signal] = []

        for idx, item in enumerate(items):
            if idx >= limit:
                break

            published_at = _parse_date(item.get("date_published"))
            if published_at:
                try:
                    if datetime.fromisoformat(published_at) < cutoff:
                        continue
                except ValueError:
                    pass

            title = item.get("title", "").strip()
            url = item.get("url", "")
            content_html = item.get("content_html", "")

            text = _html_to_text(content_html)
            sections = _split_sections(content_html)
            summary = text[:_SUMMARY_CAP]

            signals.append(
                Signal(
                    source=self.source_name,
                    source_key=self.source_key,
                    title=title,
                    url=url,
                    raw_score=len(items) - idx,
                    score=normalize_score(float(len(items) - idx), 20.0),
                    heat="",
                    summary=summary,
                    published_at=published_at,
                    content=text,
                    extra={"sections": sections, "section_count": len(sections)},
                )
            )

        return signals
