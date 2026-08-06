from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx

from .base import BaseFetcher, Signal, normalize_score

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"
_DAILYDAWN_URL = "https://dailydawn.dev/zh.json"


def _parse_date(date_str: str | None) -> str | None:
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except (ValueError, TypeError):
        return None


def _clean_html(html: str, max_len: int = 300) -> str:
    if not html:
        return ""
    from bs4 import BeautifulSoup
    clean = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return clean if len(clean) <= max_len else clean[:max_len] + "..."


class DailyDawnFetcher(BaseFetcher):
    """DailyDawn 每日黎明 AI 趋势日报抓取器。

    从 https://dailydawn.dev/zh.json 获取 JSON Feed 格式的 AI 趋势信号。
    每日更新，包含 AI 工具、模型、市场趋势等信号。
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
            summary = _clean_html(content_html)

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
                    content=content_html,
                )
            )

        return signals
