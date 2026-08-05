from __future__ import annotations

import random
from datetime import datetime, timezone

import httpx

from .base import BaseFetcher, Signal, normalize_score

SUBREDDITS = [
    "programming", "startups", "LocalLLaMA", "MachineLearning",
    "webdev", "SaaS", "opensource", "devops", "rust",
    "selfhosted", "indiehackers", "SideProject",
]

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


class RedditFetcher(BaseFetcher):
    """公开 JSON 接入（免 OAuth）。高峰期可能 429，单 sub 失败自动跳过。"""

    source_key = "reddit"
    source_name = "Reddit"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 20))
        min_ups = int(conf.get("min_ups", 20))
        signals: list[Signal] = []

        for sub in SUBREDDITS:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit}"
            try:
                resp = await client.get(
                    url,
                    timeout=self.timeout,
                    headers={"User-Agent": random.choice(USER_AGENTS)},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception:
                continue

            for child in data.get("data", {}).get("children", []):
                d = child["data"]
                ups = d.get("ups", 0)
                if ups < min_ups:
                    continue
                created_utc = d.get("created_utc")
                published_at = (
                    datetime.fromtimestamp(created_utc, tz=timezone.utc).isoformat()
                    if created_utc
                    else None
                )
                signals.append(
                    Signal(
                        source=f"Reddit /r/{sub}",
                        source_key="reddit",
                        title=d.get("title", ""),
                        url=d.get("url_overridden_by_dest")
                        or f"https://reddit.com{d.get('permalink','')}",
                        raw_score=ups,
                        score=normalize_score(ups, 2000.0),
                        comments=d.get("num_comments", 0),
                        author=d.get("author", ""),
                        tags=[sub],
                        published_at=published_at,
                    )
                )
        return signals