from __future__ import annotations

from ..config import enabled_sources, opml_config, rss_feeds, rsshub_sources
from .base import BaseFetcher, Signal
from .dailydawn import DailyDawnFetcher
from .devto import DevToFetcher
from .github_trending import GitHubTrendingFetcher
from .github_tracker import RepoTrackerFetcher
from .google_trends import GoogleTrendsFetcher
from .hackernews import HackerNewsFetcher
from .hn_ai import HnAiFetcher
from .huggingface import HuggingFaceFetcher
from .k36kr import Kr36Fetcher
from .lobsters import LobstersFetcher
from .producthunt import ProductHuntFetcher
from .reddit import RedditFetcher
from .rss import RssFetcher
from .rsshub import RsshubFetcher
from .tencent import TencentFetcher
from .toutiao import ToutiaoHotFetcher
from .twitter import TwitterFetcher
from .user_opml import UserOpmlFetcher
from .v2ex import V2EXFetcher
from .wallstreetcn import WallStreetCNFetcher
from .weibo import WeiboFetcher

# 专用 API/爬虫抓取器：key -> 类
_API_CLASSES: dict[str, type[BaseFetcher]] = {
    "hackernews": HackerNewsFetcher,
    "hn_ai": HnAiFetcher,
    "dailydawn": DailyDawnFetcher,
    "github": GitHubTrendingFetcher,
    "v2ex": V2EXFetcher,
    "producthunt": ProductHuntFetcher,
    "huggingface": HuggingFaceFetcher,
    "weibo": WeiboFetcher,
    "wallstreetcn": WallStreetCNFetcher,
    "tencent": TencentFetcher,
    "36kr": Kr36Fetcher,
    "lobsters": LobstersFetcher,
    "devto": DevToFetcher,
    "reddit": RedditFetcher,
    "toutiao": ToutiaoHotFetcher,
    "twitter": TwitterFetcher,
}

TREND_KEY = "google_trends"
USER_KEY = "user"


def _all_keys(cfg: dict) -> list[str]:
    keys = list(_API_CLASSES.keys())
    if enabled_sources(cfg).get(TREND_KEY, {}).get("enabled", True):
        keys.append(TREND_KEY)
    keys.extend(rss_feeds(cfg).keys())
    keys.extend(rsshub_sources(cfg).keys())
    keys.append(USER_KEY)
    return keys


def build_fetchers(cfg: dict) -> dict[str, BaseFetcher]:
    """根据 config 构建统一抓取器注册表 {source_key: fetcher}。"""
    src_cfg = cfg.get("sources", {})
    enabled = enabled_sources(cfg)
    fetchers: dict[str, BaseFetcher] = {}

    for key, cls in _API_CLASSES.items():
        if key in enabled:
            fetchers[key] = cls(config=src_cfg.get(key, {}))

    if TREND_KEY in enabled:
        fetchers[TREND_KEY] = GoogleTrendsFetcher(config=src_cfg.get(TREND_KEY, {}))

    for key, feed in rss_feeds(cfg).items():
        fetchers[key] = RssFetcher(config=feed, source_key=key)

    for key, conf in rsshub_sources(cfg).items():
        fetchers[key] = RsshubFetcher(config=conf, source_key=key)

    for key, f in RepoTrackerFetcher.build_fetchers(cfg).items():
        fetchers[key] = f

    fetchers[USER_KEY] = UserOpmlFetcher(config=src_cfg.get(USER_KEY, {}), opml_cfg=opml_config(cfg))

    return fetchers


def select_fetchers(
    cfg: dict, requested: list[str] | None = None
) -> dict[str, BaseFetcher]:
    """按 --source 选择抓取器；requested 为空或含 'all' 时返回全部。"""
    all_fetchers = build_fetchers(cfg)
    if not requested or "all" in requested:
        return all_fetchers
    selected: dict[str, BaseFetcher] = {}
    for key in requested:
        key = key.strip()
        if key in all_fetchers:
            selected[key] = all_fetchers[key]
    return selected