from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any

import httpx


@dataclass
class Signal:
    """统一信号数据模型（所有数据源输出该结构）。

    - source:     源显示名（如 "HackerNews" / "Reddit /r/programming"）
    - source_key: 源注册表 key（如 "hackernews"），主题分配依赖它
    - score:      归一化 0-1 分数（不同源 typical_max 不同，见各 fetcher）
    - heat:       原始热度文本（微博 "108万" 等，LLM 展示用）
    - hn_url:     Hacker News 讨论链接（如有）
    - gh_url:     GitHub 仓库链接（如有）
    - published_at: ISO 8601 UTC 字符串（无单条发布时间概念则留 None）
    - age_bucket: 由 aggregator 运行时填充（today / past_72h / older / unknown）
    - topics:     由 classifier 运行时填充（命中主题 key 列表）
    - seen_on:    跨日去重标记（最近一次被产出到日报的日期，由 state 填充）
    """

    source: str
    title: str
    url: str = ""
    source_key: str = ""
    raw_score: float = 0.0
    score: float = 0.0
    comments: int = 0
    author: str = ""
    heat: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    published_at: str | None = None
    hn_url: str = ""
    gh_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    content: str = ""
    topics: list[str] = field(default_factory=list)
    seen_on: str | None = None
    age_bucket: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


class BaseFetcher(ABC):
    """抓取器抽象基类。新数据源继承它并实现 fetch()。"""

    source_key: str = "unknown"
    source_name: str = "unknown"
    timeout: float = 15.0

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        """拉取数据并返回统一格式的 Signal 列表。"""
        raise NotImplementedError

    async def safe_fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        """容错包装：单源失败打印错误、返回空列表，不阻塞整条管线。"""
        try:
            return await self.fetch(client)
        except Exception as e:
            print(f"[{self.source_name}] fetch failed: {type(e).__name__}: {e}")
            return []


def normalize_score(raw: float, typical_max: float) -> float:
    """raw / typical_max 后裁剪到 [0, 1]。"""
    if typical_max <= 0:
        return 0.0
    return max(0.0, min(raw / typical_max, 1.0))
