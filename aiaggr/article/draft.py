from __future__ import annotations

import re

from .common import json_block, llm_stage

_EDITOR_LABELS = [
    "章节目标", "写作角度", "待核对编辑要点", "仅作编辑目标", "必须由来源支持",
    "可引用来源要点", "编辑计划", "（仅作编辑目标", "不是事实来源",
]
_STRIP_PREFIX = re.compile(r"^(章节目标|写作角度|待核对编辑要点|可引用来源要点)\s*[:：]\s*")


def _strip_editor_labels(text: str) -> str:
    lines = text.splitlines()
    out = []
    for line in lines:
        cleaned = _STRIP_PREFIX.sub("", line)
        if any(label in cleaned for label in _EDITOR_LABELS):
            continue
        out.append(cleaned)
    return "\n".join(out)


def fallback_draft(plan: dict, items: dict[str, dict]) -> str:
    """确定性兜底正文：按章节平铺来源摘要，无 AI 深度改写。"""
    blocks: list[str] = []
    for sec in plan.get("sections", []):
        blocks.append(f"## {sec.get('title', '')}")
        blocks.append("")
        key_points = sec.get("keyPoints", [])
        if key_points:
            blocks.extend(f"- {kp}" for kp in key_points)
            blocks.append("")
        for it_id in sec.get("itemIds", []):
            it = items.get(it_id)
            if not it:
                continue
            summary = (it.get("summary") or it.get("title") or "")[:400]
            blocks.append(f"**{it['title']}**：{summary}")
            blocks.append("")
    return "\n".join(blocks).strip()


async def draft_article(plan: dict, items: list[dict], evidence: dict, settings: dict, prompts_dir) -> str:
    """草稿：按文章计划写读者可读正文（只允许输入内事实）。LLM 失败走确定性兜底。"""
    item_map = {it["id"]: it for it in items}
    res = await llm_stage(
        prompts_dir, "draft", settings,
        {
            "plan_json": json_block(plan),
            "items_json": json_block(items),
            "evidence_json": json_block(evidence),
        },
        temperature=0.35,
    )
    md = str(res.get("markdown", "") or "").strip()
    if not md:
        return fallback_draft(plan, item_map)
    return _strip_editor_labels(md)