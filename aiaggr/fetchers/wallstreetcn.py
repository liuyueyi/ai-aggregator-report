from __future__ import annotations

from datetime import datetime

import httpx

from .base import BaseFetcher, Signal, normalize_score


class WallStreetCNFetcher(BaseFetcher):
    source_key = "wallstreetcn"
    source_name = "华尔街见闻"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 20))
        url = ("https://api-one.wallstcn.com/apiv1/content/information-flow"
               "?channel=global-channel&accept=article&limit=30")
        resp = await client.get(url, timeout=self.timeout)
        resp.raise_for_status()
        items = resp.json().get("data", {}).get("items", [])

        signals: list[Signal] = []
        kept = 0
        for item in items:
            res = item.get("resource")
            if not res or not (res.get("title") or res.get("content_short")):
                continue
            ts = res.get("display_time", 0)
            published_at = datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None
            signals.append(
                Signal(
                    source="华尔街见闻",
                    source_key="wallstreetcn",
                    title=res.get("title") or res.get("content_short", ""),
                    url=res.get("uri", ""),
                    raw_score=res.get("score", 0) or 0,
                    score=normalize_score(float(res.get("score", 0) or 0), 100.0),
                    author=res.get("author", {}).get("name", "") if isinstance(res.get("author"), dict) else "",
                    summary=res.get("content_short", ""),
                    published_at=published_at,
                )
            )
            kept += 1
            if kept >= limit:
                break
        return signals