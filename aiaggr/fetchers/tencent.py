from __future__ import annotations

import httpx

from .base import BaseFetcher, Signal, normalize_score


class TencentFetcher(BaseFetcher):
    source_key = "tencent"
    source_name = "腾讯新闻"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 15))
        url = "https://i.news.qq.com/web_backend/v2/getTagInfo?tagId=aEWqxLtdgmQ%3D"
        resp = await client.get(
            url,
            timeout=self.timeout,
            headers={"Referer": "https://news.qq.com/", "User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        try:
            tabs = resp.json().get("data", {}).get("tabs", [])
            article_list = tabs[0]["articleList"] if tabs else []
        except (KeyError, IndexError, TypeError):
            article_list = []

        signals: list[Signal] = []
        for news in article_list[:limit]:
            signals.append(
                Signal(
                    source="腾讯新闻",
                    source_key="tencent",
                    title=news.get("title", ""),
                    url=news.get("url") or news.get("link_info", {}).get("url", ""),
                    summary=news.get("abstract", ""),
                    published_at=news.get("pub_time", "") or news.get("publish_time", ""),
                )
            )
        return signals