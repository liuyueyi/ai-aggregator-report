from __future__ import annotations


def build_cover_plan(plan: dict, title: str, date: str) -> dict:
    """配图方案（本期只生成方案，不接图片生成 API）。

    产出：封面视觉方案 + 正文配图位布局 + 可直接投喂生图 API 的 prompt。
    """
    cd = plan.get("coverDirection", {}) or {}
    placements = (plan.get("bodyImagePlan") or {}).get("placements", [])
    cover_prompt = (
        f"中文公众号/自媒体封面图。标题语义：{title}。主题：{cd.get('textBrief') or plan.get('thesis','')}。"
        f"视觉：{cd.get('visualBrief') or '简洁、信息密度适中、留白干净'}。"
        f"氛围：{cd.get('mood') or '冷静专业'}。限制：不要出现二维码、水印、品牌 Logo、可识别人脸。"
    )
    return {
        "date": date,
        "title": title,
        "mode": "plan-only",
        "cover": {
            "visualBrief": cd.get("visualBrief", ""),
            "textBrief": cd.get("textBrief", ""),
            "mood": cd.get("mood", ""),
            "prompt": cover_prompt,
            "generator": "dashscope|minimax",   # 后续接入生图 API 时使用
            "generated": False,
        },
        "bodyImages": {
            "enabled": bool(plan.get("bodyImagePlan", {}).get("enabled", False)),
            "placements": [
                {
                    "sectionId": p.get("sectionId", ""),
                    "purpose": p.get("purpose", ""),
                    "promptHint": p.get("promptHint", ""),
                }
                for p in placements
            ],
        },
    }