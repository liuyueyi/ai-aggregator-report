from __future__ import annotations

import httpx

from ..config import env
from .base import BaseFetcher, Signal, normalize_score

_DEFAULT_BASE = "https://rsshub.app"


def _clean_html(text: str, max_len: int) -> str:
    if not text:
        return ""
    from bs4 import BeautifulSoup  # noqa: PLC0415
    clean = BeautifulSoup(text, "lxml").get_text(" ", strip=True)
    clean = " ".join(clean.split())
    return clean if len(clean) <= max_len else clean[:max_len] + "..."


class RsshubFetcher(BaseFetcher):
    """通用 RSSHub 抓取器：把公众号/小红书/头条/Twitter 等无公开 API 的平台内容
    通过 RSSHub 路由接入（RSSHub 返回 JSON 格式）。

    - 由 config 的 name/path/hours/enabled 驱动，一个条目 = 一个平台路由
    - base_url 取自 env RSSHUB_BASE_URL（默认 https://rsshub.app），config 可覆盖
    - 请求 {base}{path}?format=json&limit=N&sorted=1
    - score 按条目位置递减弱代理；正文放进 content 供深层洞察/证据补全使用
    """

    timeout = 20.0

    def __init__(self, config: dict, source_key: str):
        super().__init__(config)
        self.source_key = source_key
        self.source_name = config.get("name", source_key)
        self._path = str(config.get("path", "")).strip()
        self._base = config.get("base_url", "") or env("RSSHUB_BASE_URL", "") or _DEFAULT_BASE

    @property
    def url(self) -> str:
        seg = self._path if self._path else self.source_key
        if not seg.startswith("/"):
            seg = "/" + seg
        base = self._base.rstrip("/")
        limit = int(self.config.get("limit", 20) or 20)
        return f"{base}{seg}?format=json&limit={limit}&sorted=1"

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        conf = self.config
        limit = int(conf.get("limit", 20) or 20)
        if not self._path and not conf.get("url"):
            return []
        try:
            resp = await client.get(
                self.url,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr/0.1",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[{self.source_name}] rsshub fetch failed: {type(e).__name__}: {e}")
            return []

        if isinstance(data, dict) and data.get("status") is not True and data.get("error"):
            print(f"[{self.source_name}] rsshub error: {data.get('error')}")
            return []
        items = data.get("items", []) if isinstance(data, dict) else None
        if not isinstance(items, list):
            items = data if isinstance(data, list) else []

        signals: list[Signal] = []
        total = max(len(items), 1)
        for idx, it in enumerate(items):
            if idx >= limit:
                break
            if not isinstance(it, dict):
                continue
            title = (it.get("title") or "").strip()
            if not title:
                continue
            desc = it.get("description") or it.get("content_html") or ""
            tags = it.get("tags", [])
            signals.append(
                Signal(
                    source=self.source_name,
                    source_key=self.source_key,
                    title=title,
                    url=it.get("link") or it.get("url") or "",
                    raw_score=total - idx,
                    score=normalize_score(float(total - idx), 20.0),
                    summary=_clean_html(desc, 300),
                    content=_clean_html(desc, 2000),
                    published_at=it.get("date_published")
                    or it.get("pubDate")
                    or it.get("published")
                    or None,
                    tags=[t.get("name") or "" for t in tags] if isinstance(tags, list) else [],
                )
            )
        return signals