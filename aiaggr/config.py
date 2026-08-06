from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: str | Path | None = None) -> dict:
    """加载 config.yaml 并读取 .env。"""
    load_dotenv(ROOT / ".env")
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return cfg


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def llm_settings(cfg: dict) -> dict:
    llm = cfg.get("llm", {})
    return {
        "api_key": env(llm.get("api_key_env", "LLM_API_KEY"), ""),
        "base_url": env(llm.get("base_url_env", "LLM_BASE_URL"), ""),
        "model": env(llm.get("model_env", "LLM_MODEL"), ""),
        "timeout": llm.get("timeout", 60),
        "temperature": llm.get("temperature", 0.55),
        "max_retries": llm.get("max_retries", 4),
        "max_concurrency": max(1, int(llm.get("max_concurrency", 4))),
        "mock": bool(llm.get("mock", False)) or env("AGGR_MOCK_LLM") == "1",
    }


def timezone_name(cfg: dict) -> str:
    return cfg.get("timezone", "Asia/Shanghai")


def report_dir(cfg: dict) -> Path:
    return ROOT / cfg.get("report", {}).get("dir", "report")


def state_dir(cfg: dict) -> Path:
    return ROOT / cfg.get("state", {}).get("dir", ".state")


def enabled_topics(cfg: dict) -> dict[str, dict]:
    """返回启用的主题 {key: config}。"""
    topics = cfg.get("topics", {})
    return {k: v for k, v in topics.items() if v.get("enabled", True)}


def enabled_sources(cfg: dict) -> dict[str, dict]:
    """返回启用的源 {key: config}（含专用源 + google_trends）。"""
    sources = cfg.get("sources", {})
    out: dict[str, dict] = {}
    for key, conf in sources.items():
        if key in ("rss", "opml"):
            continue
        if conf.get("enabled", True):
            out[key] = conf
    return out


def rss_feeds(cfg: dict) -> dict[str, dict]:
    """返回启用的通用 RSS 源 {key: {name,url,hours}}。"""
    feeds = cfg.get("sources", {}).get("rss", {})
    return {k: v for k, v in feeds.items() if v.get("enabled", True)}


def opml_config(cfg: dict) -> dict[str, Any]:
    return cfg.get("opml", {})


def tracking_config(cfg: dict) -> dict[str, Any]:
    """返回 GitHub 生态追踪配置 {enabled, window_hours, cli_repos, skills_repo, agents_repos}。"""
    return cfg.get("tracking", {})


def promp_dir(cfg: dict) -> Path:
    return ROOT / "prompts"


def site_dir(cfg: dict) -> Path:
    """站点交付目录：统一收纳 index.html / manifest.json / feed.xml。"""
    return ROOT / cfg.get("site", {}).get("dir", "site")
