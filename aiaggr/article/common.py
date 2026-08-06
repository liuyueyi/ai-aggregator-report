from __future__ import annotations

import asyncio
import json

from ..fetchers.base import Signal
from ..llm import call_json, is_mock

SYSTEM = "你是资深中文媒体编辑与审稿人，严格输出 JSON，不要解释。"


def signal_to_item(s: Signal, idx: int) -> dict:
    """把 Signal 序列化为 LLM 可读的紧凑条目（article 工作流的原子单位）。"""
    return {
        "id": f"c{idx}",
        "title": s.title,
        "url": s.url,
        "source": s.source,
        "source_key": s.source_key,
        "score": round(s.score, 2),
        "heat": s.heat,
        "age_bucket": s.age_bucket,
        "published_at": s.published_at,
        "summary": (s.summary or s.title)[:300],
        "content": (s.content or "")[:1500],
    }


def json_block(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


_NOISY_HOSTS = {
    "zhihu", "weixin.qq.com", "mp.weixin.qq.com", "csdn", "juejin", "toutiao.com",
    "sina", "sina.cn", "youtube.com", "instagram.com", "facebook.com", "linkedin.com",
    "bilibili.com", "douyin.com", "xiaohongshu.com", "tieba.baidu.com",
}

NOISY_HOSTS = set(_NOISY_HOSTS)

_OFFICIAL_HOSTS = {
    "openai.com", "anthropic.com", "deepmind.google", "google.com", "microsoft.com",
    "github.com", "meta.com", "x.ai", "apple.com", "nvidia.com", "deepseek.com",
    "baidu.com", "alibaba.com", "tencent.com", "huggingface.co", "openai.org",
    "gov", "mil", "edu", "ac.cn",
}
_PRIMARY_HOSTS = {
    "arxiv.org", "paperswithcode.com", "pubmed.ncbi.nlm.nih.gov", "acm.org",
    "ieee.org", "semanticscholar.org", "ssrn.com", "biorxiv.org",
}
_COMMUNITY_HOSTS = {
    "x.com", "twitter.com", "reddit.com", "news.ycombinator.com", "v2ex.com",
    "producthunt.com", "github.com", "lobste.rs", "dev.to",
}
_MEDIA_HOSTS = {
    "techcrunch.com", "theverge.com", "wired.com", "36kr.com", "qbitai.com",
    "jiqizhixin.com", "aibase.com", "ithome.com", "solidot.org", "reuters.com",
    "bloomberg.com", "ft.com", "bbc.com", "theguardian.com",
}


def host_source_type(url: str) -> str:
    """按域名判断证据来源类型：official/primary/media/community/background。"""
    host = _host_of(url)
    if not host:
        return "background"
    if any(h in host for h in _OFFICIAL_HOSTS):
        return "official"
    if any(h in host for h in _PRIMARY_HOSTS):
        return "primary"
    if any(h in host for h in _MEDIA_HOSTS):
        return "media"
    if any(h in host for h in _COMMUNITY_HOSTS):
        return "community"
    return "background"


def is_noisy_host(url: str) -> bool:
    host = _host_of(url)
    return any(h in host for h in _NOISY_HOSTS)


def confidence_for(source_type: str) -> str:
    if source_type in ("official", "primary"):
        return "high"
    if source_type in ("media", "community"):
        return "medium"
    return "low"


async def llm_stage(
    prompts_dir,
    name: str,
    settings: dict,
    placeholders: dict[str, str],
    temperature: float = 0.3,
    system: str = SYSTEM,
) -> dict:
    """统一 LLM 阶段调用：mock/失败返回 {}，由调用方走确定性 fallback。"""
    if is_mock(settings):
        return {}
    tpl = (prompts_dir / f"article.{name}.md").read_text(encoding="utf-8")
    user = tpl
    for k, v in placeholders.items():
        user = user.replace("{{" + k + "}}", v)
    try:
        res = await asyncio.to_thread(call_json, system, user, settings, temperature=temperature)
    except Exception as e:  # noqa: BLE001
        print(f"[article:{name}] LLM failed, fallback: {type(e).__name__}: {e}")
        return {}
    return res if isinstance(res, dict) else {}


def clamp(v, lo: float = 0.0, hi: float = 100.0) -> float:
    try:
        return max(lo, min(float(v), hi))
    except (TypeError, ValueError):
        return lo
