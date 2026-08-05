from __future__ import annotations

import asyncio
import time

import httpx

from .base import BaseFetcher, Signal, normalize_score

# 与 agents-radar 对齐：6 组 AI 关键词并行查询，覆盖社区最活跃的 AI 讨论面
AI_QUERIES = [
    "AI",
    "LLM",
    "Claude",
    "OpenAI",
    "Anthropic",
    "machine learning",
]

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


class HnAiFetcher(BaseFetcher):
    """Hacker News AI 热帖：6 组 Algolia 查询并行抓取过去 N 小时帖子，
    去重后按分数排序取 top N（默认 30），供社区情绪分析。"""

    source_key = "hn_ai"
    source_name = "HN AI"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        window_hours = int(conf.get("window_hours", 24))
        hits_per_page = int(conf.get("hits_per_page", 50))
        limit = int(conf.get("limit", 30))
        cutoff = int(time.time()) - window_hours * 3600

        async def query(q: str) -> list[dict]:
            params = {
                "query": q,
                "tags": "story",
                "numericFilters": f"created_at_i>{cutoff}",
                "hitsPerPage": hits_per_page,
            }
            resp = await client.get(ALGOLIA_URL, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json().get("hits", [])

        # 6 组并行查询，单组失败不阻塞其它组
        results = await asyncio.gather(
            *[query(q) for q in AI_QUERIES], return_exceptions=True
        )

        seen: dict[str, Signal] = {}
        for q, hits in zip(AI_QUERIES, results):
            if isinstance(hits, BaseException):
                continue
            for hit in hits:
                hn_id = hit.get("objectID", "")
                if not hn_id or hn_id in seen:
                    continue
                points = hit.get("points", 0)
                story_url = hit.get("url") or ""
                seen[hn_id] = Signal(
                    source=self.source_name,
                    source_key=self.source_key,
                    title=hit.get("title", ""),
                    url=story_url,
                    raw_score=points,
                    score=normalize_score(points, 500.0),
                    comments=hit.get("num_comments", 0),
                    author=hit.get("author", ""),
                    published_at=hit.get("created_at"),
                    hn_url=f"https://news.ycombinator.com/item?id={hn_id}",
                    tags=[q],
                    extra={"hn_id": hn_id, "matched_query": q},
                )

        ranked = sorted(seen.values(), key=lambda s: s.raw_score, reverse=True)[:limit]
        return ranked
