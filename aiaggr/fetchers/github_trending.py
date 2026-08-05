from __future__ import annotations

from bs4 import BeautifulSoup
import httpx

from .base import BaseFetcher, Signal, normalize_score


class GitHubTrendingFetcher(BaseFetcher):
    source_key = "github"
    source_name = "GitHub Trending"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 25))
        resp = await client.get(
            "https://github.com/trending?since=daily",
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1"},
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        signals: list[Signal] = []
        for article in soup.select("article.Box-row")[:limit]:
            link = article.select_one("h2 a")
            if not link:
                continue
            repo = link.get("href", "").strip("/")
            title = repo
            desc_el = article.select_one("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""

            stars_today = 0
            today_el = article.find("span", class_="d-inline-block float-sm-right")
            if today_el:
                try:
                    stars_today = int("".join(c for c in today_el.get_text() if c.isdigit()))
                except ValueError:
                    pass

            lang_el = article.select_one("[itemprop=programmingLanguage]")
            lang = lang_el.get_text(strip=True) if lang_el else ""

            stars_el = article.select_one('a[href$="/stargazers"]')
            stars_text = stars_el.get_text(strip=True) if stars_el else ""

            signals.append(
                Signal(
                    source="GitHub Trending",
                    source_key="github",
                    title=title,
                    url=f"https://github.com/{repo}",
                    raw_score=stars_today,
                    score=normalize_score(stars_today, 1000.0),
                    summary=desc,
                    heat=stars_text,
                    tags=[lang] if lang else [],
                    gh_url=f"https://github.com/{repo}",
                )
            )
        return signals
