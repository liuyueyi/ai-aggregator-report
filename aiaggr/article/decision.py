from __future__ import annotations

from .common import json_block, llm_stage

_FORMATS = {
    "daily-brief", "deep-analysis", "product-review", "trend-analysis",
    "tutorial", "interview", "mixed",
}


def normalize_decision(res: dict, topic_report: dict, items: list[dict]) -> dict:
    reports = topic_report.get("scores", [])
    clusters = topic_report.get("clusters", [])
    cluster_by_id = {c["id"]: c for c in clusters}
    valid_ids = set(cluster_by_id)
    item_urls = {it["url"] for it in items}

    lead_id = str(res.get("leadTopicId", ""))
    if lead_id not in valid_ids:
        lead_id = max(reports, key=lambda s: s.get("finalScore", 0), default={}).get("topicId", "")
        if lead_id not in valid_ids and clusters:
            lead_id = clusters[0]["id"]

    fmt = str(res.get("recommendedFormat", "mixed"))
    if fmt not in _FORMATS:
        fmt = "daily-brief" if len(clusters) > 2 else "mixed"

    selected: list[dict] = []
    for t in res.get("selectedTopics", []):
        if not isinstance(t, dict):
            continue
        tid = str(t.get("topicId", ""))
        if tid not in valid_ids:
            continue
        role = str(t.get("role", "supporting"))
        if tid == lead_id:
            role = "lead"
        selected.append({"topicId": tid, "role": role, "reason": str(t.get("reason", ""))})
    lead_seen = any(s["topicId"] == lead_id for s in selected)
    if not lead_seen:
        selected.insert(0, {"topicId": lead_id, "role": "lead", "reason": "主线"})
    selected = selected[:6]

    skipped = [
        {"topicId": str(t["topicId"]), "reason": str(t.get("reason", ""))}
        for t in res.get("skippedTopics", [])
        if isinstance(t, dict) and str(t.get("topicId", "")) in valid_ids and
        str(t.get("topicId", "")) not in {s["topicId"] for s in selected}
    ]
    for s in reports:
        tid = s.get("topicId")
        if tid in valid_ids and tid != lead_id and tid not in {x["topicId"] for x in selected} and \
                tid not in {x["topicId"] for x in skipped}:
            skipped.append({"topicId": tid, "reason": "未入选"})

    dr = res.get("duplicationRisk", {})
    level = str((dr or {}).get("level", "low"))
    if level not in {"low", "medium", "high"}:
        level = "low"

    judgements = []
    for j in res.get("sourceJudgements", []):
        if isinstance(j, dict) and j.get("url") in item_urls:
            role = str(j.get("role", "reference-only"))
            if role not in {"primary", "supporting", "reference-only", "avoid"}:
                role = "reference-only"
            judgements.append({"url": j["url"], "role": role, "reason": str(j.get("reason", ""))})
    judgements = judgements[:20]

    return {
        "leadTopicId": lead_id,
        "leadTopicTitle": cluster_by_id.get(lead_id, {}).get("title", ""),
        "decisionSummary": str(res.get("decisionSummary", "")).strip()
        or cluster_by_id.get(lead_id, {}).get("summary", ""),
        "whyThisNow": list(res.get("whyThisNow", []))[:4],
        "recommendedFormat": fmt,
        "selectedTopics": selected,
        "skippedTopics": skipped,
        "duplicationRisk": {"level": level, "reason": str((dr or {}).get("reason", "")),
                            "avoidAngles": list((dr or {}).get("avoidAngles", []))[:4]},
        "sourceJudgements": judgements,
        "writingDirectives": list(res.get("writingDirectives", []))[:8],
        "titleWarnings": list(res.get("titleWarnings", []))[:6],
        "fallback": res.get("fallback", False),
    }


def fallback_decision(topic_report: dict) -> dict:
    clusters = topic_report.get("clusters", [])
    scores = topic_report.get("scores", [])
    cluster_by_id = {c["id"]: c for c in clusters}
    if not clusters:
        return {
            "leadTopicId": "", "leadTopicTitle": "", "decisionSummary": "", "whyThisNow": [],
            "recommendedFormat": "mixed", "selectedTopics": [], "skippedTopics": [],
            "duplicationRisk": {"level": "low", "reason": "", "avoidAngles": []},
            "sourceJudgements": [], "writingDirectives": [], "titleWarnings": [], "fallback": True,
        }
    lead = max(clusters, key=lambda c: next((s.get("finalScore", 0) for s in scores if s["topicId"] == c["id"]), 0))
    fmt = "daily-brief" if len(clusters) > 2 else "mixed"
    selected = [{"topicId": lead["id"], "role": "lead", "reason": "主线"}]
    skipped = [{"topicId": c["id"], "reason": "未入选"} for c in clusters if c["id"] != lead["id"]]
    return {
        "leadTopicId": lead["id"], "leadTopicTitle": lead["title"], "decisionSummary": lead.get("summary", ""),
        "whyThisNow": ["确定性兜底编辑决策（LLM 不可用）"], "recommendedFormat": fmt,
        "selectedTopics": selected, "skippedTopics": skipped,
        "duplicationRisk": {"level": "medium", "reason": "未完成 AI 编辑决策", "avoidAngles": []},
        "sourceJudgements": [], "writingDirectives": [], "titleWarnings": [], "fallback": True,
    }


async def create_decision(topic_report: dict, items: list[dict], settings: dict, prompts_dir, date: str, profile: dict) -> dict:
    if not topic_report.get("clusters"):
        return fallback_decision(topic_report)
    res = await llm_stage(
        prompts_dir, "decision", settings,
        {
            "date": date,
            "profile": json_block(profile),
            "topics_json": json_block(topic_report),
            "items_json": json_block(items),
        },
        temperature=0.25,
    )
    if res.get("leadTopicId") or res.get("selectedTopics"):
        return normalize_decision(res, topic_report, items)
    return fallback_decision(topic_report)