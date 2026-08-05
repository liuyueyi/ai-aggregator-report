from __future__ import annotations

from bs4 import BeautifulSoup
import httpx

from .base import BaseFetcher, Signal, normalize_score


class Kr36Fetcher(BaseFetcher):
    """36Kr 快讯（HTML 爬取，页面结构变更可能失效，失败自动降级为空）。"""

    source_key = "36kr"
    source_name = "36氪"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 15))
        resp = await client.get(
            "https://36kr.com/newsflashes",
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"},
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        signals: list[Signal] = []
        total = 0
        for item in soup.select(".newsflash-item"):
            title_el = item.select_one(".item-title")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            url = href if href.startswith("http") else f"https://36kr.com{href}"
            time_el = item.select_one(".time")
            signals.append(
                Signal(
                    source="36氪",
                    source_key="36kr",
                    title=title,
                    url=url,
                    raw_score=total,
                    score=normalize_score(float(total), 15.0),
                    published_at=time_el.get_text(strip=True) if time_el else None,
                )
            )
            total += 1
            if total >= limit:
                break
        return signals