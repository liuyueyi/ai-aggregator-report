from __future__ import annotations

import asyncio
import os

import httpx

from .base import BaseFetcher, Signal, normalize_score

GITHUB_API = "https://api.github.com"

# 模块级：与 agents-radar / 用户指定的追踪仓库保持一致
DEFAULT_CLI_REPOS = [
    {"repo": "anthropics/claude-code", "name": "Claude Code"},
    {"repo": "openai/codex", "name": "OpenAI Codex"},
    {"repo": "google-gemini/gemini-cli", "name": "Gemini CLI"},
    {"repo": "github/copilot-cli", "name": "GitHub Copilot CLI"},
    {"repo": "MoonshotAI/kimi-cli", "name": "Kimi Code CLI"},
    {"repo": "anomalyco/opencode", "name": "OpenCode"},
    {"repo": "QwenLM/qwen-code", "name": "Qwen Code"},
    {"repo": "Hmbown/DeepSeek-TUI", "name": "DeepSeek TUI"},
]
DEFAULT_SKILLS_REPO = {"repo": "anthropics/skills", "name": "Claude Code Skills"}
DEFAULT_AGENTS_REPOS = [
    {"repo": "openclaw/openclaw", "name": "OpenClaw"},
    {"repo": "HKUDS/nanobot", "name": "NanoBot"},
    {"repo": "sipeed/picoclaw", "name": "PicoClaw"},
    {"repo": "zeroclaw-labs/zeroclaw", "name": "ZeroClaw"},
    {"repo": "nousresearch/hermes-agent", "name": "Hermes Agent"},
    {"repo": "agentscope-ai/CoPaw", "name": "CoPaw"},
]


def gh_auth_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-aggregator-report"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class RepoTrackerFetcher(BaseFetcher):
    """通用 GitHub 仓库追踪器：抓取若干仓库的开放 Issues/PRs 与 Releases，
    按社区活跃度（评论数）量化。CLI 工具 / Skills 与 AI Agent 生态两类各用一个实例。"""

    source_key = "tracker"
    source_name = "GitHub Tracker"

    def __init__(
        self,
        config: dict | None = None,
        *,
        key: str,
        name: str,
        repos: list[dict],
        issues_per_repo: int = 5,
        releases_per_repo: int = 3,
    ):
        super().__init__(config=config)
        self.source_key = key
        self.source_name = name
        self.repos = repos
        self.issues_per_repo = issues_per_repo
        self.releases_per_repo = releases_per_repo

    async def fetch(self, client: httpx.AsyncClient) -> list[Signal]:
        headers = gh_auth_headers()
        loops: list[Signal] = []

        async def fetch_repo(entry: dict) -> list[Signal]:
            repo = entry["repo"]
            name = entry.get("name", repo.split("/")[-1])
            out: list[Signal] = []
            gh_url = f"https://github.com/{repo}"
            threads: list = []

            threads.append(
                client.get(
                    f"{GITHUB_API}/repos/{repo}/issues",
                    params={"state": "open", "sort": "comments", "direction": "desc",
                            "per_page": self.issues_per_repo},
                    headers=headers,
                    timeout=self.timeout,
                )
            )
            threads.append(
                client.get(
                    f"{GITHUB_API}/repos/{repo}/releases",
                    params={"per_page": self.releases_per_repo},
                    headers=headers,
                    timeout=self.timeout,
                )
            )
            responses = await asyncio.gather(*threads, return_exceptions=True)
            issue_resp, release_resp = responses

            if not isinstance(issue_resp, BaseException) and issue_resp.is_success:
                for it in issue_resp.json():
                    comments = it.get("comments", 0)
                    is_pr = "pull_request" in it
                    out.append(
                        Signal(
                            source=f"{name} ({'PR' if is_pr else 'Issue'})",
                            source_key=self.source_key,
                            title=it.get("title", ""),
                            url=it.get("html_url", gh_url),
                            raw_score=float(comments),
                            score=normalize_score(float(comments), 100.0),
                            comments=comments,
                            author=(it.get("user") or {}).get("login", ""),
                            heat=f"{comments} 评论",
                            published_at=it.get("created_at"),
                            gh_url=gh_url,
                            tags=["issue" if not is_pr else "pr"],
                            extra={"repo": repo, "project": name, "kind": "issue" if not is_pr else "pr"},
                        )
                    )
            else:
                print(f"[{self.source_key}:{repo}] issues/PRs 拉取失败")

            if not isinstance(release_resp, BaseException) and release_resp.is_success:
                for rl in release_resp.json():
                    out.append(
                        Signal(
                            source=name,
                            source_key=self.source_key,
                            title=f"{name} 发布 {rl.get('tag_name', '')}",
                            url=rl.get("html_url", gh_url),
                            raw_score=0.0,
                            score=0.0,
                            heat=self._tag_text(rl.get("name"), rl.get("tag_name")),
                            published_at=rl.get("published_at"),
                            gh_url=gh_url,
                            tags=["release"],
                            extra={"repo": repo, "project": name, "kind": "release"},
                        )
                    )
            else:
                print(f"[{self.source_key}:{repo}] releases 拉取失败")
            return out

        results = await asyncio.gather(*[fetch_repo(r) for r in self.repos], return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                continue
            loops.extend(r)
        return loops

    @staticmethod
    def _tag_text(name: str | None, tag: str | None) -> str:
        return (name or tag or "").strip() or ""

    @staticmethod
    def build_fetchers(cfg: dict) -> dict[str, "RepoTrackerFetcher"]:
        """根据 tracking 配置实例化 cli_tracker / agents_tracker（无配置则用默认仓库列表）。"""
        track = cfg.get("tracking", {})
        if not track.get("enabled", True):
            return {}
        base_cfg = cfg.get("sources", {}).get("tracking", {})
        if not base_cfg.get("enabled", True):
            return {}
        window_hours = int(track.get("window_hours", 24))
        issues_per_repo = int(base_cfg.get("issues_per_repo", 5))
        releases_per_repo = int(base_cfg.get("releases_per_repo", 3))
        cfg_cli = track.get("cli_repos") or DEFAULT_CLI_REPOS
        cfg_agents = track.get("agents_repos") or DEFAULT_AGENTS_REPOS
        skills = track.get("skills_repo") or DEFAULT_SKILLS_REPO
        cli_repos = [*cfg_cli]
        if skills:
            cli_repos.append(skills)
        out: dict[str, RepoTrackerFetcher] = {}
        if cfg_cli or skills:
            out["cli_tracker"] = RepoTrackerFetcher(
                key="cli_tracker", name="AI CLI / Skills",
                repos=cli_repos, issues_per_repo=issues_per_repo,
                releases_per_repo=releases_per_repo,
            )
        if cfg_agents:
            out["agents_tracker"] = RepoTrackerFetcher(
                key="agents_tracker", name="AI Agent 生态",
                repos=cfg_agents, issues_per_repo=issues_per_repo,
                releases_per_repo=releases_per_repo,
            )
        return out