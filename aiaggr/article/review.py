from __future__ import annotations

from .common import clamp, json_block, llm_stage
from .title import _is_low_quality

_ACTIONS = {"publish", "dry-run-only", "revise", "block"}
_CATEGORIES = {"fact", "title", "structure", "tone", "html", "risk"}


def normalize_review(res: dict) -> dict:
    dims = {k: clamp(res.get("dimensionScores", {}).get(k, 70)) for k in
            ("factConsistency", "titleQuality", "structureQuality", "expressionQuality", "riskHandling")}
    overall = clamp(res.get("overallScore"))
    if not res.get("overallScore") and overall == 0:
        overall = sum(dims.values()) / len(dims)

    action = str(res.get("recommendedAction", ""))
    if action not in _ACTIONS:
        if any(i.get("severity") == "blocker" or
               (i.get("category") == "fact" and i.get("severity") in ("high", "blocker"))
               for i in res.get("issues", [])):
            action = "block"
        elif overall >= 80:
            action = "publish"
        elif overall >= 60:
            action = "dry-run-only"
        elif overall >= 40:
            action = "revise"
        else:
            action = "block"

    issues: list[dict] = []
    for i in res.get("issues", []):
        if not isinstance(i, dict):
            continue
        cat = str(i.get("category", ""))
        sev = str(i.get("severity", "low"))
        if cat not in _CATEGORIES or sev not in {"low", "medium", "high", "blocker"}:
            continue
        issues.append({
            "category": cat, "severity": sev, "message": str(i.get("message", "")),
            "evidence": str(i.get("evidence", "")), "suggestion": str(i.get("suggestion", "")),
            "autoFixable": bool(i.get("autoFixable", False)),
        })
    issues = issues[:8]

    # 一致性守卫：无 issue 却要求 revise/block/不放行 → 从最弱维度合成一条
    if not issues and (action in ("revise", "block") or not res.get("allowPublish", True) or overall < 80):
        weakest = min(dims, key=dims.get)
        sev = "blocker" if action == "block" or overall < 50 else "high"
        issues.append({
            "category": "structure" if weakest == "structureQuality" else "tone",
            "severity": sev, "message": f"{weakest} 维度未达发布标准（当前 {dims[weakest]:.0f} 分）",
            "evidence": "", "suggestion": "针对最弱维度定向修订后复审", "autoFixable": True,
        })

    allow = bool(res.get("allowPublish", action == "publish"))
    if action == "block" and allow:
        allow = False
    return {
        "overallScore": round(overall, 1),
        "allowPublish": allow,
        "recommendedAction": action,
        "summary": str(res.get("summary", "")).strip(),
        "dimensionScores": {k: round(v, 1) for k, v in dims.items()},
        "issues": issues,
        "repairSuggestions": list(res.get("repairSuggestions", []))[:6],
        "fallback": res.get("fallback", False),
    }


def fallback_review(title: str, markdown: str, plan: dict) -> dict:
    issues: list[dict] = []
    if _is_low_quality(title):
        issues.append({"category": "title", "severity": "high", "message": "标题含营销腔/栏目腔",
                       "evidence": title, "suggestion": "改用客观直述标题", "autoFixable": True})
    for w in ("可能", "或将", "据传", "有消息称", "内部人士"):
        if w in markdown:
            issues.append({"category": "fact", "severity": "medium", "message": f"出现未证实表述『{w}』",
                           "evidence": w, "suggestion": "删除或补充来源", "autoFixable": True})
            break
    html_bad = []
    for tag in ("<div", "<script", "<style", "<svg", "class=", "id=", "onclick"):
        if tag in markdown:
            html_bad.append(tag)
    if html_bad:
        issues.append({"category": "html", "severity": "high", "message": "正文含微信不兼容标签/属性",
                       "evidence": ",".join(html_bad), "suggestion": "清洗为纯 markdown/微信兼容 HTML", "autoFixable": True})
    base = 78
    score = max(50.0, base - len(issues) * 8)
    action = "revise" if score < 70 else "publish"
    if any(i["severity"] in ("high", "blocker") for i in issues):
        action = "revise"
        score = min(score, 66)
    return {
        "overallScore": round(score, 1),
        "allowPublish": action == "publish",
        "recommendedAction": action,
        "summary": "确定性审稿（LLM 不可用）",
        "dimensionScores": {"factConsistency": round(min(score + 4, 95), 1), "titleQuality": round(min(score, 90), 1),
                            "structureQuality": round(min(score + 2, 92), 1), "expressionQuality": round(min(score, 90), 1),
                            "riskHandling": round(min(score + 1, 90), 1)},
        "issues": issues,
        "repairSuggestions": [i["suggestion"] for i in issues],
        "fallback": True,
    }


async def review_article(title: str, markdown: str, plan: dict, items: list[dict], evidence: dict,
                         settings: dict, prompts_dir, date: str) -> dict:
    res = await llm_stage(
        prompts_dir, "review", settings,
        {
            "date": date,
            "title": title,
            "markdown": markdown[:16000],
            "plan_json": json_block(plan),
            "items_json": json_block(items),
            "evidence_json": json_block(evidence),
        },
        temperature=0.2,
    )
    if res.get("overallScore") is not None or res.get("issues"):
        return normalize_review(res)
    return fallback_review(title, markdown, plan)