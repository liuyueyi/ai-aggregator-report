from __future__ import annotations

import asyncio
import hashlib
import re

import httpx

from ..config import env
from .common import NOISY_HOSTS, confidence_for, host_source_type

_JINA_READER = "https://r.jina.ai/"
_TIMEOUT = 20.0
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) aiaggr-article/0.1"


def _query_tokens(topic_report: dict, decision: dict) -> list[str]:
    tokens: list[str] = []
    lead_id = decision.get("leadTopicId", "")
    for c in topic_report.get("clusters", []):
        if not lead_id or c["id"] == lead_id:
            tokens.append(c.get("title", ""))
            tokens.extend(c.get("keywords", []))
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        t = str(t).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:12]


def _overlap(text: str, tokens: list[str]) -> list[str]:
    matched: list[str] = []
    for t in tokens:
        if t and len(t) >= 2 and t.lower() in text.lower():
            matched.append(t)
    return matched[:8]


def _relevance_score(source_type: str, confidence: str, overlap_n: int) -> float:
    s = 0.0
    s += {"official": 18, "primary": 16, "media": 10, "community": 6, "background": 2}.get(source_type, 2)
    s += {"high": 12, "medium": 8, "low": 4}.get(confidence, 4)
    s += min(overlap_n, 8) * 4
    return s


def _stable_id(url: str, title: str) -> str:
    key = f"{url}:{title}"
    return "ev_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


async def _hydrate(url: str, max_chars: int = 1200) -> str:
    """Jina Reader 正文抓取（有 JINA_API_KEY 走认证，否则降级普通抓取）。"""
    jina_key = env("JINA_API_KEY", "").strip()
    headers = {"User-Agent": _UA}
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT, headers=headers) as client:
            resp = await client.get(_JINA_READER + url)
            resp.raise_for_status()
            text = resp.text
        text = re.sub(r"[\n\r]+", "\n", text)
        return " ".join(text.split())[:max_chars]
    except Exception:  # noqa: BLE001
        return await _plain_fetch(url, max_chars)


async def _plain_fetch(url: str, max_chars: int) -> str:
    from ..deep import fetch_url_content

    async with httpx.AsyncClient(follow_redirects=True, timeout=_TIMEOUT, headers={"User-Agent": _UA}) as client:
        return await fetch_url_content(client, url, max_chars=max_chars)


async def build_evidence_pack(
    topic_report: dict,
    decision: dict,
    items: list[dict],
    cfg: dict,
) -> dict:
    """证据补全（确定性）：从候选池 + 深度补抓构建证据链。

    返回 {"topic", "queries", "items", "gaps", "fallback"}，其中 items 为 EvidenceItem：
    {id, title, url, sourceType, confidence, supports, summary}。
    """
    ev_cfg = cfg.get("article", {}).get("evidence", {})
    if not ev_cfg.get("enabled", True):
        return {"topic": decision.get("leadTopicTitle", ""), "queries": [], "items": [], "gaps": [], "fallback": False}
    max_items = int(ev_cfg.get("max_items", 5) or 5)
    max_hydration = int(ev_cfg.get("max_hydration", 3) or 3)
    noisy = set(NOISY_HOSTS) | set(ev_cfg.get("noisy_hosts") or [])

    tokens = _query_tokens(topic_report, decision)
    lead_id = decision.get("leadTopicId", "")

    candidates: list[dict] = []
    for it in items:
        if it.get("url") and it["url"] not in noisy:
            text = (it.get("content") or "") + " " + (it.get("summary") or "") + " " + (it.get("title") or "")
            candidates.append({
                "title": it["title"], "url": it["url"], "text": text[:1500], "source_key": it.get("source_key", ""),
            })
    seen_urls: set[str] = set()

    hydration_targets = [
        it for it in items
        if (not lead_id or it["id"] == lead_id or it.get("score", 0) >= 0.6) and it.get("url") and not it.get("content") and it["url"] not in noisy
    ][:max_hydration]
    for it in hydration_targets:
        body = await _hydrate(it["url"])
        if body:
            candidates.append({
                "title": it["title"], "url": it["url"], "text": body, "source_key": it.get("source_key", ""),
            })
            await asyncio.sleep(0.1)

    out: list[dict] = []
    for c in candidates:
        if c["url"] in seen_urls:
            continue
        seen_urls.add(c["url"])
        st = host_source_type(c["url"])
        conf = confidence_for(st)
        supports = _overlap(c["text"], tokens)
        if not supports and not tokens:
            supports = _overlap(c["text"], [c["title"]])
        out.append({
            "id": _stable_id(c["url"], c["title"]),
            "title": c["title"],
            "url": c["url"],
            "sourceType": st,
            "confidence": conf,
            "supports": supports,
            "summary": (c["text"] or c["title"])[:400],
            "_score": _relevance_score(st, conf, len(supports)),
        })

    out.sort(key=lambda x: -x["_score"])
    out = out[:max_items]
    for e in out:
        e.pop("_score", None)
    gaps = [t for t in tokens if not any(t in e["supports"] for e in out)]
    return {
        "topic": decision.get("leadTopicTitle", ""),
        "queries": tokens,
        "items": out,
        "gaps": gaps[:4],
        "fallback": False,
    }