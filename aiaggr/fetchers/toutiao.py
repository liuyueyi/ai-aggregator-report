from __future__ import annotations

import httpx

from .base import BaseFetcher, Signal, normalize_score

_HOT_BOARD = "https://www.toutiao.com/hot-event/hot-board/"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)

# 热榜热度量级（热点值最高可达千万级），用作归一化 typical_max
_TYPICAL_MAX = 10_000_000.0


def _parse_item(item: dict, idx: int) -> Signal | None:
    title = (item.get("Title") or "").strip()
    url = (item.get("Url") or "").strip()
    if not title:
        return None
    try:
        raw = float(item.get("HotValue") or 0)
    except (TypeError, ValueError):
        raw = 0.0
    if raw <= 0:
        raw = float(max(1, 60 - idx))
    summary = (item.get("Label") or "").strip()
    return Signal(
        source="头条热榜",
        source_key="toutiao",
        title=title[:200],
        url=url or "https://www.toutiao.com",
        raw_score=raw,
        score=normalize_score(raw, _TYPICAL_MAX),
        comments=0,
        author="",
        heat=str(int(raw)) if raw else "",
        summary=summary[:300],
        content=summary[:500],
        published_at=None,
        extra={"cluster_id": str(item.get("ClusterId", "") or "")[:80]},
    )


class ToutiaoHotFetcher(BaseFetcher):
    """头条热榜专用抓取器（直接命中公开 PC 热榜接口，不依赖 RSSHub）。

    - GET https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc
    - 返回 JSON data[]，每项 Title / Url / HotValue / Label
    - 平台无公开 API，若接口被反爬/改版则 fail-open 返回空
    """

    source_key = "toutiao"
    source_name = "头条热榜"
    timeout = 15.0

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self._limit = int(self.config.get("limit", 20) or 20)

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        resp = await client.get(
            _HOT_BOARD,
            params={"origin": "toutiao_pc"},
            headers={"User-Agent": _UA},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
        out: list[Signal] = []
        for idx, item in enumerate(data):
            sig = _parse_item(item, idx)
            if not sig:
                continue
            out.append(sig)
            if len(out) >= self._limit:
                break
        return out