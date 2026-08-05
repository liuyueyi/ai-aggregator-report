from __future__ import annotations

import httpx

from .base import BaseFetcher, Signal, normalize_score


class DevToFetcher(BaseFetcher):
    source_key = "devto"
    source_name = "Dev.to"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 15))
        resp = await client.get(
            "https://dev.to/api/articles?top=1&per_page=30",
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()

        signals: list[Signal] = []
        for art in data[:limit]:
            reactions = art.get("positive_reactions_count", 0)
            tag_list = art.get("tag_list", [])
            if isinstance(tag_list, str):
                tag_list = [t for t in tag_list.split(",") if t]
            signals.append(
                Signal(
                    source="Dev.to",
                    source_key="devto",
                    title=art.get("title", ""),
                    url=art.get("url", ""),
                    raw_score=reactions,
                    score=normalize_score(reactions, 500.0),
                    author=art.get("user", {}).get("name", ""),
                    summary=art.get("description", ""),
                    tags=tag_list,
                    published_at=(art.get("published_at") or "")[:10],
                )
            )
        return signals