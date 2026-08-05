from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import BaseFetcher, Signal, normalize_score


class V2EXFetcher(BaseFetcher):
    source_key = "v2ex"
    source_name = "V2EX"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 20))
        resp = await client.get(
            "https://www.v2ex.com/api/topics/hot.json",
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"},
        )
        resp.raise_for_status()
        topics = resp.json()

        signals: list[Signal] = []
        for t in topics[:limit]:
            replies = t.get("replies", 0)
            created_ts = t.get("created")
            published_at = (
                datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()
                if created_ts
                else None
            )
            signals.append(
                Signal(
                    source="V2EX",
                    source_key="v2ex",
                    title=t.get("title", ""),
                    url=t.get("url", ""),
                    raw_score=replies,
                    score=normalize_score(replies, 200.0),
                    comments=replies,
                    author=t.get("member", {}).get("username", ""),
                    tags=[t.get("node", {}).get("title", "")] if t.get("node") else [],
                    published_at=published_at,
                )
            )
        return signals
