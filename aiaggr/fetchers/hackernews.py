from __future__ import annotations

import time

import httpx

from .base import BaseFetcher, Signal, normalize_score


class HackerNewsFetcher(BaseFetcher):
    source_key = "hackernews"
    source_name = "HackerNews"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        window_hours = int(conf.get("window_hours", 48))
        min_points = int(conf.get("min_points", 20))
        limit = int(conf.get("limit", 60))
        cutoff = int(time.time()) - window_hours * 3600

        url = "https://hn.algolia.com/api/v1/search"
        params = {
            "tags": "story",
            "numericFilters": f"points>{min_points},created_at_i>{cutoff}",
            "hitsPerPage": max(limit, 60),
        }
        resp = await client.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()

        signals: list[Signal] = []
        for hit in data.get("hits", []):
            story_url = hit.get("url") or ""
            points = hit.get("points", 0)
            hn_id = hit.get("objectID", "")
            signals.append(
                Signal(
                    source="HackerNews",
                    source_key="hackernews",
                    title=hit.get("title", ""),
                    url=story_url,
                    raw_score=points,
                    score=normalize_score(points, 500.0),
                    comments=hit.get("num_comments", 0),
                    author=hit.get("author", ""),
                    published_at=hit.get("created_at"),
                    hn_url=f"https://news.ycombinator.com/item?id={hn_id}",
                    extra={"hn_id": hn_id},
                )
            )
        return signals
