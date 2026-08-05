from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import feedparser

from .base import BaseFetcher, Signal, normalize_score

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"


def _entry_time(entry) -> str | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    return None


def _clean_summary(text: str, max_len: int = 300) -> str:
    if not text:
        return ""
    from bs4 import BeautifulSoup  # noqa: PLC0415
    clean = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    return clean if len(clean) <= max_len else clean[:max_len] + "..."


class RssFetcher(BaseFetcher):
    """通用 RSS/Atom 抓取器，由一个 feed 配置（name/url/hours）驱动。

    - hours>0 时只保留最近 N 小时内条目，解析不出时间的条目 fail-open 保留
    - score 按条目标题位置递减（RSS 无统一热度，取序作为弱代理）
    """

    timeout = 20.0

    def __init__(self, config: dict, source_key: str):
        super().__init__(config)
        self.source_key = source_key
        self.source_name = config.get("name", source_key)
        self._url = config.get("url", "")
        self._hours = int(config.get("hours", 0) or 0)

    async def fetch(self, client) -> list[Signal]:
        return await asyncio.to_thread(self._fetch_sync)

    def _fetch_sync(self) -> list[Signal]:
        limit = self.config.get("limit", 15)
        try:
            feed = feedparser.parse(self._url, request_headers={"User-Agent": _UA})
        except Exception as e:
            print(f"[{self.source_name}] rss parse failed: {e}")
            return []
        if not feed.entries:
            return []

        cutoff = None
        if self._hours > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=self._hours)

        entries = feed.entries
        total = max(len(entries), 1)
        signals: list[Signal] = []
        for idx, e in enumerate(entries):
            if idx >= limit:
                break
            published_at = _entry_time(e)
            if cutoff and published_at:
                try:
                    if datetime.fromisoformat(published_at) < cutoff:
                        continue
                except ValueError:
                    pass
            link = e.get("link", "")
            signals.append(
                Signal(
                    source=self.source_name,
                    source_key=self.source_key,
                    title=e.get("title", "").strip(),
                    url=link,
                    raw_score=total - idx,
                    score=normalize_score(float(total - idx), 20.0),
                    heat="",
                    summary=_clean_summary(e.get("summary", "")),
                    published_at=published_at,
                )
            )
        return signals