from __future__ import annotations

import asyncio
from typing import Iterable

import httpx

from .fetchers.base import Signal

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr-deep/0.1"
_TIMEOUT = 20.0
_DEFAULT_MAX_CHARS = 3000


async def fetch_url_content(client: httpx.AsyncClient, url: str, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """抓取单个 URL 正文纯文本（截断到 max_chars）。失败静默返回空串。"""
    if not url:
        return ""
    try:
        resp = await client.get(url)
        resp.raise_for_status()
    except Exception:
        return ""
    try:
        from bs4 import BeautifulSoup  # noqa: PLC0415
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())
    except Exception:
        text = resp.text
    return text[:max_chars]


async def enrich_with_content(signals: Iterable[Signal], max_chars: int = _DEFAULT_MAX_CHARS, concurrency: int = 10) -> None:
    """并发为 signals 拉取正文写入 Signal.content。已有 content 或 URL 为空则跳过，单条失败不阻塞。"""
    todo = [s for s in signals if s.url and not s.content]
    if not todo:
        return
    sem = asyncio.Semaphore(concurrency)

    async def one(s: Signal) -> None:
        async with sem:
            s.content = await fetch_url_content(client, s.url, max_chars)

    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT, headers={"User-Agent": _UA}) as client:
        await asyncio.gather(*(one(s) for s in todo))
