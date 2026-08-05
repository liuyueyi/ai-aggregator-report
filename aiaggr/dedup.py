from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .fetchers.base import Signal

# 跟踪参数：去重比对时忽略（保留其余 query，保证 weibo 等按标题区分的链接不被合并）
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "ref_src", "spm", "share", "from", "referral",
    "source", "sid", "scm",
}

_WS_RE = re.compile(r"[\s\u3000]+")


def canonical_url(url: str, ignore_tracking: bool = True) -> str:
    """规范化 URL 用于去重：小写 host、去除跟踪参数、保留有意义 query、去尾斜杠。"""
    try:
        parts = urlsplit(url.strip())
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/")
        if ignore_tracking and parts.query:
            kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                    if k.lower() not in _TRACKING_PARAMS]
            query = urlencode(sorted(kept))
        else:
            query = parts.query
        return urlunsplit((parts.scheme, netloc, path, query, ""))
    except Exception:
        return url.strip()


def _is_trivial_key(key: str) -> bool:
    """形如 https://host 或空串的 key 无法区分不同文章，视为无效。"""
    return (not key) or key in {"http://", "https://", "http:///", "https:///"}


def normalized_title(title: str) -> str:
    """标题归一化：去空白与常见噪音，用于无 URL 时的指纹兜底。"""
    t = _WS_RE.sub(" ", (title or "")).strip().lower()
    t = re.sub(r"^\[[^\]]+\]\s*", "", t)  # 去掉 [AINews] 之类前缀
    return t


def fingerprint(signal: Signal, ignore_tracking: bool = True) -> str:
    """稳定的信号指纹（跨日去重用）。优先 URL，无 URL 时回退归一化标题。"""
    if signal.url and signal.url.startswith("http"):
        key = canonical_url(signal.url, ignore_tracking)
        if not _is_trivial_key(key):
            return hashlib.sha1(key.encode("utf-8")).hexdigest()
    return hashlib.sha1(normalized_title(signal.title).encode("utf-8")).hexdigest()


def _compute_age_bucket(published_at: str | None, today: date) -> str:
    if not published_at:
        return "unknown"
    try:
        raw = published_at.replace("Z", "+00:00")
        pub_date = datetime.fromisoformat(raw).astimezone(timezone.utc).date()
    except Exception:
        return "unknown"
    days_ago = (today - pub_date).days
    if days_ago <= 0:
        return "today"
    if days_ago <= 3:
        return "past_72h"
    return "older"


def aggregate(
    signals: list[Signal],
    *,
    today: date | None = None,
    ignore_tracking: bool = True,
) -> list[Signal]:
    """同日聚合去重：canonical URL 去重 + 跨源同 URL 分数叠加。

    - 同 URL 跨源出现 → 分数叠加（evidence 更强）
    - 无有效 URL 的条目按序号保留（不合并）
    - 为每个信号计算 age_bucket（today / past_72h / older / unknown）
    """
    today = today or datetime.now(timezone.utc).date()
    bucket: dict[str, Signal] = {}
    fallback_idx = 0

    for s in signals:
        key = canonical_url(s.url, ignore_tracking) if s.url.startswith("http") else ""
        if _is_trivial_key(key):
            key = f"__nourl__{fallback_idx}"
            fallback_idx += 1
            bucket[key] = s
            continue

        if key in bucket:
            existing = bucket[key]
            existing.score = min(existing.score + s.score * 0.5, 1.5)
            existing.raw_score += s.raw_score
            existing.extra.setdefault("also_on", []).append(s.source)
            if s.hn_url and not existing.hn_url:
                existing.hn_url = s.hn_url
            if s.gh_url and not existing.gh_url:
                existing.gh_url = s.gh_url
        else:
            bucket[key] = s

    ranked = sorted(bucket.values(), key=lambda x: x.score, reverse=True)
    for s in ranked:
        s.age_bucket = _compute_age_bucket(s.published_at, today)
    return ranked
