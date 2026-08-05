from __future__ import annotations

import warnings
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup
from bs4 import XMLParsedAsHTMLWarning
import httpx

from .base import BaseFetcher, Signal, normalize_score

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


class ProductHuntFetcher(BaseFetcher):
    """Product Hunt 免 token 接入：解析官方 RSS feed。"""

    source_key = "producthunt"
    source_name = "Product Hunt"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 20))
        resp = await client.get(
            "https://www.producthunt.com/feed",
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        signals: list[Signal] = []
        entries = soup.find_all(["item", "entry"])[:limit]
        total = max(len(entries), 1)
        for idx, entry in enumerate(entries):
            title_tag = entry.find("title")
            link_tag = entry.find("link")
            url = ""
            if link_tag:
                url = link_tag.get("href") or link_tag.get_text(strip=True) or ""
            pub_box = entry.find("pubDate") or entry.find("published")
            pub_str = pub_box.get_text(strip=True) if pub_box else ""
            published_at = None
            if pub_str:
                try:
                    published_at = parsedate_to_datetime(pub_str).isoformat()
                except Exception:
                    pass
            signals.append(
                Signal(
                    source="Product Hunt",
                    source_key="producthunt",
                    title=title_tag.get_text(strip=True) if title_tag else "",
                    url=url,
                    raw_score=total - idx,
                    score=normalize_score(float(total - idx), 20.0),
                    heat="Top Product" if idx < 10 else "",
                    published_at=published_at,
                )
            )
        return signals
