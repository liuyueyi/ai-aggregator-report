from __future__ import annotations

from urllib.parse import quote

import httpx

from ..config import env
from .base import BaseFetcher, Signal, normalize_score

_TWITTERAPI_IO = "https://api.twitterapi.io/twitter/tweet/advanced_search"
_XQUIK = "https://xquik.com/api/v1/x/tweets/search"
_CONTRACT = "2026-04-29"


def _tweet_url(screen_name: str, tweet_id: str) -> str:
    return f"https://x.com/{screen_name}/status/{tweet_id}"


def _pick_tweets(data: dict) -> list[dict]:
    """兼容 TwitterAPI.io / Xquik 的不同返回形态。"""
    if isinstance(data.get("data"), dict):
        inner = data["data"]
        tweets = inner.get("tweets") or inner.get("items") or []
        if isinstance(tweets, list):
            return tweets
        if isinstance(inner.get("results"), list):
            return inner["results"]
    if isinstance(data.get("data"), list):
        return data["data"]
    if isinstance(data.get("tweets"), list):
        return data["tweets"]
    if isinstance(data.get("results"), list):
        return data["results"]
    return []


def _parse_tweet(t: dict, screen_name: str) -> Signal | None:
    text = t.get("text") or t.get("content") or t.get("tweet") or ""
    if isinstance(text, dict):
        text = text.get("text", "")
    text = str(text).strip()
    tid = t.get("id") or t.get("id_str") or t.get("tweet_id") or ""
    if not text or not tid:
        return None
    url = t.get("url") or _tweet_url(screen_name, str(tid))
    likes = int(t.get("like_count") or t.get("favorite_count") or 0)
    rts = int(t.get("retweet_count") or 0)
    replies = int(t.get("reply_count") or 0)
    heat = likes + rts * 2
    created = (
        t.get("created_at")
        or t.get("createdAt")
        or t.get("date")
        or t.get("timestamp")
        or None
    )
    # 简化 ISO 时间（Twitter 返回如 "Tue Aug 05 12:00:00 +0000 2026"）
    published_at = None
    if created and "T" in str(created):
        published_at = str(created)
    else:
        try:
            from datetime import datetime

            published_at = datetime.strptime(str(created), "%a %b %d %H:%M:%S %z %Y").isoformat()
        except (ValueError, TypeError):
            published_at = None
    return Signal(
        source=f"X /@{screen_name}",
        source_key="twitter",
        title=text.splitlines()[0][:200],
        url=url,
        raw_score=float(heat),
        score=normalize_score(float(heat), 1000.0),
        comments=replies,
        author=screen_name,
        heat=str(heat),
        summary=text[:300],
        content=text[:2000],
        published_at=published_at,
    )


class TwitterFetcher(BaseFetcher):
    """Twitter/X 专用抓取器（双后端，参考 ai-trend-publish twitter-scraper）。

    - 首选 TwitterAPI.io：X-API-Key 头（env TWITTER_API_KEY）
    - 失败 fallback Xquik：x-api-key 头（env XQUIK_API_KEY）+ 契约头
    - config.accounts: [screen_name, ...]，每个账号查近 24h 非回复推文
    - 两者都未配置 key 时返回空并提示
    """

    source_key = "twitter"
    source_name = "Twitter/X"
    timeout = 25.0

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._io_key = env("TWITTER_API_KEY", "").strip()
        self._xquik_key = env("XQUIK_API_KEY", "").strip()

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        if not self._io_key and not self._xquik_key:
            print("[Twitter/X] 未配置 TWITTER_API_KEY / XQUIK_API_KEY，跳过（RSSHub /twitter 路由可作备选）")
            return []
        accounts = self.config.get("accounts") or [self.config.get("account")] or []
        accounts = [a for a in accounts if a]
        if not accounts:
            accounts = ["OpenAIDevs"]
        limit = int(self.config.get("limit", 20) or 20)

        out: list[Signal] = []
        for acc in accounts:
            acc = acc.strip().strip("@")
            query = f"from:{acc} -filter:replies within_time:24h"
            tweets = await self._fetch_one(client, query)
            seen: set[str] = set()
            for t in tweets:
                sig = _parse_tweet(t, acc)
                if not sig:
                    continue
                if sig.url in seen:
                    continue
                seen.add(sig.url)
                out.append(sig)
                if len(out) >= limit:
                    return out
        return out

    async def _fetch_one(self, client: httpx.AsyncClient, query: str) -> list[dict]:
        if self._io_key:
            try:
                resp = await client.get(
                    _TWITTERAPI_IO,
                    params={"query": query, "queryType": "Top"},
                    headers={"X-API-Key": self._io_key},
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return _pick_tweets(resp.json())
            except Exception as e:
                print(f"[Twitter/X] twitterapi.io failed: {type(e).__name__}: {e}")
        if self._xquik_key:
            try:
                resp = await client.get(
                    _XQUIK,
                    params={"q": query, "queryType": "Top", "limit": 20},
                    headers={
                        "x-api-key": self._xquik_key,
                        "xquik-api-contract": _CONTRACT,
                    },
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                return _pick_tweets(resp.json())
            except Exception as e:
                print(f"[Twitter/X] xquik failed: {type(e).__name__}: {e}")
        return []