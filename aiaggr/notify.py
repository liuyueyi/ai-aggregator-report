from __future__ import annotations

import asyncio
import os

import httpx

# 飞书自定义机器人 Webhook（多群用英文逗号分隔），未配置则静默跳过。
# 也兼容旧版单 URL 变量 FEISHU_WEBHOOK_URL。
FEISHU_ENV = "FEISHU_WEBHOOK_URLS"
FEISHU_ENV_LEGACY = "FEISHU_WEBHOOK_URL"

_WEBHOOK_TIMEOUT = 15.0


def feishu_webhook_urls() -> list[str]:
    raw = os.environ.get(FEISHU_ENV) or os.environ.get(FEISHU_ENV_LEGACY) or ""
    return [u.strip() for u in raw.split(",") if u.strip()]


def _pages_url() -> str:
    return (os.environ.get("PAGES_URL") or "").rstrip("/")


def build_feishu_card(date: str, entries: list[dict]) -> tuple[str, str]:
    """构造飞书 interactive 卡片：标题 + 各主题直达链接（Web UI hash 路由）+ tagline。"""
    base = _pages_url()
    lines = [f"📡 **AI 聚合日报 · {date}**"]
    for e in entries:
        key = e.get("key", "")
        name = e.get("name", key)
        tagline = e.get("tagline", "")
        lines.append("")
        if base and key:
            lines.append(f"• [{name}]({base}/#{date}/{key})")
        else:
            lines.append(f"• {name}")
        if tagline:
            lines.append(f"  ◦ {tagline}")
    if base:
        lines.append(f"\n[🌐 Web UI]({base})  ·  [⊕ RSS]({base}/feed.xml)")
    return f"📡 AI 聚合日报 · {date}", "\n".join(lines)


async def _post_one(client: httpx.AsyncClient, url: str, title: str, content: str) -> None:
    resp = await client.post(
        url,
        headers={"Content-Type": "application/json"},
        json={
            "msg_type": "interactive",
            "card": {
                "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
                "elements": [{"tag": "markdown", "content": content}],
            },
        },
        timeout=_WEBHOOK_TIMEOUT,
    )
    resp.raise_for_status()


async def send_feishu(title: str, content: str) -> bool:
    """向所有已配置的飞书群推送卡片；无配置返回 False（调用方静默跳过）。"""
    urls = feishu_webhook_urls()
    if not urls:
        return False
    async with httpx.AsyncClient(timeout=_WEBHOOK_TIMEOUT) as client:
        results = await asyncio.gather(
            *[_post_one(client, u, title, content) for u in urls], return_exceptions=True
        )
    ok = sum(1 for r in results if not isinstance(r, BaseException))
    for u, r in zip(urls, results):
        if isinstance(r, BaseException):
            print(f"✗ 飞书推送失败: {u}: {r}")
    print(f"→ 飞书推送：{ok}/{len(urls)} 个群成功")
    return ok > 0
