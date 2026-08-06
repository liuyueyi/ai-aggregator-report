from __future__ import annotations

from .common import clamp, json_block, llm_stage

_VALID_USES = {"lead", "brief", "skip", "watch"}
_HIGH_RISK_PATTERNS = [
    "价格为", "收费", "订阅制", "/月", "/年",
    "全面开放", "向所有人开放", "开放给",
    "取代", "替代了", "淘汰",
    "论文证明", "研究证实", "相关研究",
    "官方宣布", "正式发布", "上线",
]


def _grounding_guard(cluster: dict, items: dict[str, dict]) -> tuple[bool, str]:
    """高风险断言是否在候选源文本里出现；未出现则压级到 watch。"""
    body = ""
    for it_id in cluster.get("itemIds", []):
        it = items.get(it_id, {})
        body += " " + (it.get("title") or "") + " " + (it.get("summary") or "")[:400] + " " + (it.get("content") or "")
    body_l = body.lower()
    for pat in _HIGH_RISK_PATTERNS:
        if pat in str(cluster.get("title", "")).lower() and pat not in body_l:
            return False, f"『{pat}』类断言未见直接来源"
    return True, ""


def normalize_topic_report(res: dict, items: list[dict]) -> dict:
    valid_ids = {it["id"] for it in items}
    item_map = {it["id"]: it for it in items}

    clusters: list[dict] = []
    for c in res.get("clusters", []):
        if not isinstance(c, dict):
            continue
        ids = [i for i in c.get("itemIds", []) if i in valid_ids]
        if not ids:
            continue
        primary = c.get("primaryItemId")
        if primary not in ids:
            primary = ids[0]
        clusters.append({
            "id": str(c.get("id", f"topic-{len(clusters) + 1}")),
            "title": str(c.get("title", "")).strip() or (item_map.get(primary, {}).get("title", "")),
            "summary": str(c.get("summary", "")).strip(),
            "keywords": list(c.get("keywords", []))[:8],
            "itemIds": ids[:6],
            "primaryItemId": primary,
        })

    id_set = {c["id"] for c in clusters}
    scores: list[dict] = []
    existing = {s.get("topicId"): s for s in res.get("scores", []) if isinstance(s, dict)}
    for c in clusters:
        raw = existing.get(c["id"], {})
        use = str(raw.get("recommendedUse", "watch"))
        if use not in _VALID_USES:
            use = "watch"
        final = clamp(raw.get("finalScore", 0))
        scores.append({
            "topicId": c["id"],
            "novelty": clamp(raw.get("novelty", 50)),
            "relevance": clamp(raw.get("relevance", 50)),
            "impact": clamp(raw.get("impact", 40)),
            "evidence": clamp(raw.get("evidence", 30)),
            "actionability": clamp(raw.get("actionability", 40)),
            "saturation": clamp(raw.get("saturation", 25)),
            "risk": clamp(raw.get("risk", 30)),
            "finalScore": final,
            "recommendedUse": use,
            "reason": str(raw.get("reason", "")).strip(),
        })

    # 接地守卫：高风险断言缺来源 → 压级
    for score in scores:
        cluster = next((c for c in clusters if c["id"] == score["topicId"]), None)
        if not cluster:
            continue
        ok, reason = _grounding_guard(cluster, item_map)
        if not ok:
            score.update({"evidence": min(score["evidence"], 35), "risk": max(score["risk"], 85),
                          "finalScore": min(score["finalScore"], 45), "recommendedUse": "watch"})
            score["reason"] = (score["reason"] + "；" if score["reason"] else "") + f"守卫: {reason}"

    scores.sort(key=lambda x: x["finalScore"], reverse=True)
    return {"clusters": clusters, "scores": scores, "fallback": res.get("fallback", False)}


def fallback_topic_report(items: list[dict], max_topics: int) -> dict:
    """确定性兜底：每篇候选独立成 cluster，按条目分数 + 时效给出推荐用途。"""
    ranked = sorted(items, key=lambda it: -it.get("score", 0))
    picked = ranked[:max_topics]
    clusters, scores = [], []
    for i, it in enumerate(picked):
        cid = f"topic-{i + 1}"
        use = "lead" if i == 0 else ("brief" if i <= 2 else "watch")
        score = 30 + round(it.get("score", 0) * 60)
        score += {"today": 8, "today_window": 8, "past_72h": 3, "older": 0, "unknown": 2}.get(it.get("age_bucket", ""), 2)
        score = int(clamp(score, 10, 92))
        clusters.append({
            "id": cid, "title": it["title"], "summary": (it.get("summary") or it["title"])[:200],
            "keywords": list(it.get("tags", []))[:5], "itemIds": [it["id"]], "primaryItemId": it["id"],
        })
        scores.append({
            "topicId": cid, "novelty": 50, "relevance": 55, "impact": 40, "evidence": 35,
            "actionability": 50, "saturation": 20, "risk": 25, "finalScore": score,
            "recommendedUse": use, "reason": "确定性兜底选题（LLM 不可用）",
        })
    scores.sort(key=lambda x: x["finalScore"], reverse=True)
    return {"clusters": clusters, "scores": scores, "fallback": True}


async def create_topic_report(items: list[dict], settings: dict, prompts_dir, date: str, profile: dict, max_topics: int = 8) -> dict:
    """选题聚类：把候选条目聚类成主题并 8 维评分 + 推荐用途。"""
    top = items[:max_topics * 3]
    res = await llm_stage(
        prompts_dir, "topic", settings,
        {
            "date": date,
            "profile": json_block(profile),
            "max_topics": str(max_topics),
            "items_json": json_block(top),
        },
        temperature=0.3,
    )
    if res.get("clusters"):
        report = normalize_topic_report(res, items)
    else:
        report = fallback_topic_report(items, max_topics)
    items_map = {it["id"]: it for it in items}
    for c in report["clusters"]:
        it = items_map.get(c.get("primaryItemId", ""), {})
        c.setdefault("age_bucket", it.get("age_bucket", ""))
    return report