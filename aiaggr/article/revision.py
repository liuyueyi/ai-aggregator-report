from __future__ import annotations

from .common import json_block, llm_stage
from .draft import _strip_editor_labels


async def revise_article(
    title: str,
    markdown: str,
    plan: dict,
    review: dict,
    items: list[dict],
    settings: dict,
    prompts_dir,
) -> tuple[str, str, bool]:
    """修订：仅处理安全审稿问题，最小修改。无安全问题或失败 → 返回原稿(不采用)。

    返回 (title, markdown, applied)。
    """
    safe = review.get("issues", [])
    if not safe:
        return title, markdown, False
    res = await llm_stage(
        prompts_dir, "revision", settings,
        {
            "title": title,
            "markdown": markdown[:18000],
            "review_json": json_block({"issues": safe}),
            "plan_json": json_block(plan),
            "items_json": json_block(items),
        },
        temperature=0.25,
    )
    new_title = str(res.get("title", "") or "").strip() or title
    new_md = str(res.get("markdown", "") or "").strip()
    if not new_md:
        return title, markdown, False
    # 最小修改保护：修订不应产出空/极短正文
    if len(new_md) < max(50, int(len(markdown) * 0.5)):
        return title, markdown, False
    return _trunc_title(new_title), _strip_editor_labels(new_md), True


def _trunc_title(t: str) -> str:
    return t[:60] or t


def accept_revision(before: dict, after: dict) -> bool:
    """只在质量不降级且未引入新 blocker 时采纳修订。"""
    rank = {"block": 0, "revise": 1, "dry-run-only": 2, "publish": 3}
    before_block = any(i.get("severity") == "blocker" for i in before.get("issues", [])) or before.get("recommendedAction") == "block"
    after_block = any(i.get("severity") == "blocker" for i in after.get("issues", [])) or after.get("recommendedAction") == "block"
    if after_block and not before_block:
        return False
    if before.get("allowPublish") and not after.get("allowPublish"):
        return False
    br = rank.get(before.get("recommendedAction"), 1)
    ar = rank.get(after.get("recommendedAction"), 1)
    if ar > br:
        return True
    if ar < br:
        return False
    return float(after.get("overallScore", 0)) >= float(before.get("overallScore", 0))