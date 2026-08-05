from __future__ import annotations

from urllib.parse import quote

import httpx

from .base import BaseFetcher, Signal, normalize_score


class WeiboFetcher(BaseFetcher):
    source_key = "weibo"
    source_name = "微博热搜"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 30))
        resp = await client.get(
            "https://weibo.com/ajax/side/hotSearch",
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://weibo.com/",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        realtime = data.get("data", {}).get("realtime", [])

        signals: list[Signal] = []
        for item in realtime[:limit]:
            title = item.get("note", "") or item.get("word", "")
            if not title:
                continue
            heat = int(item.get("num", 0) or 0)
            url = f"https://s.weibo.com/weibo?q={quote(title)}&Refer=top"
            signals.append(
                Signal(
                    source="微博热搜",
                    source_key="weibo",
                    title=title,
                    url=url,
                    raw_score=heat,
                    score=normalize_score(heat, 1_000_000.0),
                    heat=str(heat),
                )
            )
        return signals