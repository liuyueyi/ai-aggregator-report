from __future__ import annotations

from datetime import datetime

import httpx

from .base import BaseFetcher, Signal, normalize_score


class LobstersFetcher(BaseFetcher):
    source_key = "lobsters"
    source_name = "Lobsters"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 15))
        resp = await client.get(
            "https://lobste.rs/hottest.json",
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"},
        )
        resp.raise_for_status()
        data = resp.json()

        signals: list[Signal] = []
        for story in data[:limit]:
            score = story.get("score", 0)
            created = story.get("created_at", "")
            published_at = None
            if created:
                try:
                    published_at = datetime.fromisoformat(created.replace("Z", "+00:00")).isoformat()
                except ValueError:
                    pass
            signals.append(
                Signal(
                    source="Lobsters",
                    source_key="lobsters",
                    title=story.get("title", ""),
                    url=story.get("url") or story.get("comments_url", ""),
                    raw_score=score,
                    score=normalize_score(score, 100.0),
                    comments=story.get("comment_count", 0),
                    tags=story.get("tags", []),
                    published_at=published_at,
                    extra={"comments_url": story.get("comments_url", "")},
                )
            )
        return signals