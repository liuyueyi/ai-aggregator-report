from __future__ import annotations

import asyncio
import os
from pathlib import Path
from xml.etree import ElementTree as ET

from .base import BaseFetcher, Signal
from .rss import RssFetcher


def find_opml_file(paths: list[str]) -> Path | None:
    """按优先级查找 OPML 文件（支持 ~ 展开）。"""
    for p in paths or []:
        q = Path(os.path.expanduser(p))
        if q.exists():
            return q.resolve()
    return None


def parse_opml(path: Path) -> list[dict]:
    """解析 OPML 2.0，返回 [{title, url, topic}]；只有 xmlUrl 的 outline 会被收集。"""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        print(f"[User OPML] parse failed: {e}")
        return []
    out: list[dict] = []
    for outline in tree.iter("outline"):
        url = outline.get("xmlUrl")
        if not url:
            continue
        out.append(
            {
                "title": outline.get("title") or outline.get("text") or "",
                "url": url,
                "topic": outline.get("data-topic") or None,
            }
        )
    return out


class UserOpmlFetcher(BaseFetcher):
    """用户自定义订阅源：解析 OPML 里的多个 RSS/Atom 源并统一抓取。

    - 主题归属：outline 带 data-topic 优先；否则匹配 opml.topic_map 关键字；
      最后回落 opml.default_topic。
    """

    source_key = "user"
    source_name = "User OPML"

    def __init__(self, config: dict, opml_cfg: dict | None = None):
        super().__init__(config)
        self.opml_cfg = opml_cfg or {}

    def _load_feeds(self) -> list[dict]:
        paths = self.opml_cfg.get("paths", [])
        path = find_opml_file(paths)
        if not path:
            print("[User OPML] no OPML file found; skipping")
            return []
        return parse_opml(path)

    def _map_topic(self, feed: dict) -> str:
        if feed.get("topic"):
            return feed["topic"]
        topic_map = self.opml_cfg.get("topic_map") or {}
        name = (feed.get("title") or "").lower()
        for keyword, topic in topic_map.items():
            if keyword.lower() in name:
                return topic
        return self.opml_cfg.get("default_topic", "general")

    def _fetch_one(self, feed: dict, limit: int) -> list[Signal]:
        topic = self._map_topic(feed)
        fetcher = RssFetcher(
            {"name": feed.get("title") or feed["url"], "url": feed["url"], "limit": limit},
            source_key="user",
        )
        signals = fetcher._fetch_sync()
        for s in signals:
            s.topics = [topic]
        return signals

    async def fetch(self, client) -> list[Signal]:
        limit = int(self.config.get("limit", 15) or 15)
        feeds = self._load_feeds()
        if not feeds:
            return []
        results = await asyncio.gather(
            *[asyncio.to_thread(self._fetch_one, feed, limit) for feed in feeds]
        )
        merged: list[Signal] = []
        for sigs in results:
            merged.extend(sigs)
        return merged