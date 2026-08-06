from __future__ import annotations

import asyncio
import time

from .base import BaseFetcher, Signal, normalize_score


def _patch_urllib3_retry_alias() -> None:
    """urllib3 2.0 把 Retry.method_whitelist 改名 allowed_methods，pytrends 4.9.2 仍用旧名。
    在导入 pytrends 前把旧关键字翻译成新关键字，保证十acity>=8/urllib3>=2 下可运行。"""
    try:
        import urllib3.util.retry as ur
    except ImportError:
        return
    retry_init = ur.Retry.__init__

    def _compat_init(self, *args, **kwargs):  # noqa: ANN001
        if "method_whitelist" in kwargs:
            kwargs.setdefault("allowed_methods", kwargs.pop("method_whitelist"))
        retry_init(self, *args, **kwargs)

    if "method_whitelist" not in getattr(ur.Retry, "_method_whitelist_compat", ()):
        ur.Retry.__init__ = _compat_init
        ur.Retry._method_whitelist_compat = True

# 关注关键词集：跨 7 天比较前半周 vs 后半周 hourly 均值的增幅
SEED_KEYWORDS = [
    "ai agent", "claude code", "llm local", "vibe coding", "indie hackers",
    "saas boilerplate", "vector database", "agent memory", "prompt engineering",
    "open source llm", "llm fine tuning", "cloudflare workers", "vercel ai",
    "hugging face", "ollama", "langchain", "rag", "agentic workflow", "mcp",
]

_BATCH_SIZE = 5
_INTER_BATCH_SLEEP = 2.0

# 连通性探测：在不可达网络（如 GFW 环境）下快速失败，避免 pytrends 逐 batch 重试拖慢管线
_PROBE_URL = "https://trends.google.com/trends/explore"
_PROBE_TIMEOUT = 3.0


class GoogleTrendsFetcher(BaseFetcher):
    """pytrends 查 Google Trends 关键词 7 日搜索增幅。

    同步库用 asyncio.to_thread 避免阻塞事件循环。pytrends 对 Google 未公开接口，
    可能偶发 429，单 batch 失败不影响其他，全部失败则降级为空。
    """

    source_key = "google_trends"
    source_name = "Google Trends"
    timeout = 30.0

    async def fetch(self, client) -> list[Signal]:
        if not await self._reachable(client):
            return []
        return await asyncio.to_thread(self._fetch_sync)

    async def _reachable(self, client) -> bool:
        """短超时探测 trends.google.com；连不通说明网络不可达，直接跳过。"""
        try:
            async with client.stream("GET", _PROBE_URL, timeout=_PROBE_TIMEOUT) as resp:
                ok = resp.status_code < 500
            return ok
        except Exception as err:
            print(f"[Google Trends] 连通性探测失败，跳过: {type(err).__name__}")
            return False

    def _fetch_sync(self) -> list[Signal]:
        _patch_urllib3_retry_alias()
        from pytrends.request import TrendReq  # noqa: PLC0415

        conf = self.config
        min_growth_pct = float(conf.get("min_growth_pct", 20.0))

        try:
            py = TrendReq(hl="en-US", tz=0, timeout=(3, 6), retries=1, backoff_factor=0.3)
        except Exception as err:
            print(f"[Google Trends] init failed: {err}")
            return []

        signals: list[Signal] = []
        for batch in _chunks(SEED_KEYWORDS, _BATCH_SIZE):
            try:
                py.build_payload(batch, timeframe="now 7-d", geo="")
                df = py.interest_over_time()
            except Exception as err:
                print(f"[Google Trends:{batch}] query failed: {type(err).__name__}: {err}")
                time.sleep(_INTER_BATCH_SLEEP)
                continue

            if df is None or df.empty:
                time.sleep(_INTER_BATCH_SLEEP)
                continue

            for kw in batch:
                if kw not in df.columns:
                    continue
                series = df[kw].astype(float).values
                if len(series) < 4:
                    continue
                half = len(series) // 2
                early = float(series[:half].mean())
                late = float(series[half:].mean())
                if early < 1.0:
                    continue
                growth = (late - early) / early * 100.0
                if growth < min_growth_pct:
                    continue

                signals.append(
                    Signal(
                        source="Google Trends",
                        source_key="google_trends",
                        title=f'"{kw}" +{growth:.0f}% (7d)',
                        url=f"https://trends.google.com/trends/explore?q={kw.replace(' ', '+')}",
                        raw_score=int(growth),
                        score=normalize_score(growth, 500.0),
                        summary=(
                            f"'{kw}' search interest rose {growth:.0f}% comparing "
                            f"late-week vs early-week in the past 7 days."
                        ),
                        tags=["search_trend", "buyer_intent"],
                        extra={"keyword": kw, "growth_pct_7d": round(growth, 1)},
                    )
                )

            time.sleep(_INTER_BATCH_SLEEP)

        return signals


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]