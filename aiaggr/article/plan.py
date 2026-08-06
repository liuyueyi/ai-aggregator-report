from __future__ import annotations

import re

from .common import json_block, llm_stage

_FORMATS = {
    "daily-brief", "deep-analysis", "product-review", "trend-analysis",
    "tutorial", "interview", "mixed",
}
_DEEP_FORMATS = {"deep-analysis", "product-review", "trend-analysis"}
_ENTITY_RE = re.compile(r"[A-Z][A-Za-z0-9]{2,}(\s[A-Z][A-Za-z0-9]{2,}){0,3}")


def _ground_entities(sections: list[dict], items: dict[str, dict]) -> list[str]:
    """把章节里未被任何源文本支撑的专名实体标记出来（接地守卫）。"""
    corpus = " ".join(
        (it.get("title", "") or "") + " " + (it.get("summary", "") or "")[:500] + " " + (it.get("content", "") or "")
        for it in items.values()
    )
    corpus_l = corpus.lower()
    notes: list[str] = []
    for sec in sections:
        blob = " ".join([
            str(sec.get("title", "")), str(sec.get("intent", "")), str(sec.get("angle", "")),
            " ".join(str(k) for k in sec.get("keyPoints", [])),
        ])
        for ent in _ENTITY_RE.findall(blob):
            if len(ent.split()) > 1 or len(ent) < 4:
                continue
            if ent.lower() not in corpus_l:
                notes.append(f"章节『{sec.get('title','')}』提及实体 {ent} 但未见于源文本，正文不得扩展该实体")
    return notes


def _enforce_depth_gate(plan: dict, evidence_items: list[dict]) -> tuple[dict, bool]:
    """证据深度门禁：深度格式却无直接支撑证据 → 降级为保守梳理 daily-brief。"""
    fmt = plan.get("format", "mixed")
    direct = [
        e for e in evidence_items
        if e.get("supports") and e.get("confidence") in ("high", "medium")
    ]
    needs_depth = fmt in _DEEP_FORMATS or re.search(r"治理框架|第三方评估|方法论|安全审计|frontier governance", str(plan.get("summary", "")) + str(plan.get("thesis", "")), re.I)
    if needs_depth and not direct:
        plan["format"] = "daily-brief"
        plan["thesis"] = "基于现有线索的保守梳理，不生成深度判断"
        plan["summary"] = "当前证据不足以支撑深度分析，按信息梳理呈现"
        plan["bodyImagePlan"] = {"enabled": False, "placements": []}
        plan.setdefault("riskNotes", []).append({
            "level": "high", "issue": "缺少直接支撑证据，深度分析已降级", "handling": "仅做事实梳理，避免推断"
        })
        return plan, True
    return plan, False


def normalize_plan(res: dict, decision: dict, topic_report: dict, items: list[dict], evidence_items: list[dict]) -> dict:
    item_map = {it["id"]: it for it in items}
    clusters = {c["id"]: c for c in topic_report.get("clusters", [])}

    sections: list[dict] = []
    for s in res.get("sections", []):
        if not isinstance(s, dict):
            continue
        ids = [i for i in s.get("itemIds", []) if i in item_map]
        if not ids:
            continue
        sections.append({
            "id": str(s.get("id", f"section-{len(sections) + 1}")),
            "title": str(s.get("title", "")).strip() or item_map.get(ids[0], {}).get("title", ""),
            "intent": str(s.get("intent", "")).strip(),
            "angle": str(s.get("angle", "")).strip(),
            "itemIds": ids[:4],
            "keyPoints": list(s.get("keyPoints", []))[:6],
        })
    if not sections:
        raise ValueError("no valid sections")

    fmt = str(res.get("format", decision.get("recommendedFormat", "mixed")))
    if fmt not in _FORMATS:
        fmt = "daily-brief"

    thesis = str(res.get("thesis", "")).strip() or decision.get("decisionSummary", "") or "今日值得关注的变化"
    title_dirs = [
        {"title": str(t.get("title", "")).strip(), "angle": str(t.get("angle", "")), "reason": str(t.get("reason", ""))}
        for t in res.get("titleDirections", [])
        if isinstance(t, dict) and str(t.get("title", "")).strip()
    ]
    if not title_dirs:
        primary = item_map.get(sections[0]["itemIds"][0], {})
        title_dirs = [{"title": primary.get("title", ""), "angle": "直述", "reason": "兜底"}]

    cd = res.get("coverDirection", {}) or {}
    plan = {
        "format": fmt,
        "thesis": thesis,
        "targetReader": str(res.get("targetReader", "")).strip() or decision.get("leadTopicTitle", ""),
        "summary": str(res.get("summary", "")).strip() or thesis,
        "sections": sections,
        "titleDirections": title_dirs,
        "coverDirection": {
            "visualBrief": str(cd.get("visualBrief", "")).strip(),
            "textBrief": str(cd.get("textBrief", "")).strip() or thesis[:80],
            "mood": str(cd.get("mood", "")).strip() or "简洁专业",
        },
        "bodyImagePlan": {
            "enabled": bool((res.get("bodyImagePlan") or {}).get("enabled", False)),
            "placements": [
                {"sectionId": str(p.get("sectionId", "")), "purpose": str(p.get("purpose", "")), "promptHint": str(p.get("promptHint", ""))}
                for p in (res.get("bodyImagePlan") or {}).get("placements", [])
                if isinstance(p, dict) and str(p.get("sectionId", "")) in {x["id"] for x in sections}
            ],
        },
        "riskNotes": [
            {"level": str(r.get("level", "low")), "issue": str(r.get("issue", "")), "handling": str(r.get("handling", ""))}
            for r in res.get("riskNotes", [])
            if isinstance(r, dict) and str(r.get("level", "")) in {"low", "medium", "high"}
        ],
        "fallback": False,
    }

    # 接地守卫：未见于源的专名实体 → 追加风险注记
    for note in _ground_entities(sections, item_map):
        plan["riskNotes"].append({"level": "high", "issue": note, "handling": "正文不得扩展该实体"})

    # 证据深度门禁
    plan, downgraded = _enforce_depth_gate(plan, evidence_items)
    if downgraded:
        # 降级后重建轻量章节（仅保留前 3 条来源的梳理）
        rebuilt = []
        for sec in sections[:3]:
            rebuilt.append(sec)
        plan["sections"] = rebuilt

    lead_key = decision.get("leadTopicId", "")
    if lead_key:
        plan.setdefault("sourceArticleIds", [])
        for cid, c in clusters.items():
            if cid == lead_key:
                plan["sourceArticleIds"] = c.get("itemIds", [])[:6]
                break
    return plan


def fallback_plan(decision: dict, topic_report: dict, items: list[dict]) -> dict:
    item_map = {it["id"]: it for it in items}
    clusters = {c["id"]: c for c in topic_report.get("clusters", [])}
    lead_id = decision.get("leadTopicId", "")
    lead = clusters.get(lead_id) or (clusters.get("topic-1") if "topic-1" in clusters else (list(clusters.values()) or [{}])[0])

    chosen_ids = []
    if lead:
        chosen_ids = lead.get("itemIds", [])[:2]
    if not chosen_ids and items:
        chosen_ids = [items[0]["id"]]
    primary = item_map.get(chosen_ids[0], {}) if chosen_ids else {}

    sections = [
        {
            "id": "section-1",
            "title": primary.get("title", "今日要点"),
            "intent": "梳理主线信息",
            "angle": "直接呈现关键事实与影响",
            "itemIds": chosen_ids[:2],
            "keyPoints": [it["title"] for it in [item_map.get(i) for i in chosen_ids if i in item_map] if it],
        }
    ]
    others = [it for it in items if it["id"] not in chosen_ids][:3]
    for i, it in enumerate(others, start=2):
        sections.append({
            "id": f"section-{i}", "title": it["title"], "intent": "补充相关进展",
            "angle": "并列补充", "itemIds": [it["id"]], "keyPoints": [(it.get("summary") or it["title"])[:120]],
        })

    thesis = decision.get("decisionSummary", "") or primary.get("title", "今日值得关注的变化")
    return {
        "format": decision.get("recommendedFormat", "daily-brief"),
        "thesis": thesis,
        "targetReader": decision.get("leadTopicTitle", ""),
        "summary": thesis,
        "sections": sections,
        "titleDirections": [{"title": primary.get("title", ""), "angle": "直述", "reason": "兜底"}],
        "coverDirection": {"visualBrief": "", "textBrief": thesis[:80], "mood": "简洁专业"},
        "bodyImagePlan": {"enabled": False, "placements": []},
        "riskNotes": [{"level": "medium", "issue": "LLM 不可用，采用确定性计划", "handling": "仅做事实梳理"}],
        "fallback": True,
    }


async def create_plan(
    topic_report: dict, decision: dict, items: list[dict], evidence: dict,
    settings: dict, prompts_dir, date: str, profile: dict,
) -> dict:
    evidence_items = evidence.get("items", [])
    res = await llm_stage(
        prompts_dir, "plan", settings,
        {
            "date": date,
            "profile": json_block(profile),
            "topics_json": json_block(topic_report),
            "decision_json": json_block(decision),
            "items_json": json_block(items),
            "evidence_json": json_block(evidence),
        },
        temperature=0.3,
    )
    try:
        if res.get("sections"):
            return normalize_plan(res, decision, topic_report, items, evidence_items)
    except ValueError:
        pass
    return fallback_plan(decision, topic_report, items)