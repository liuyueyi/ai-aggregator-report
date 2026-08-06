from __future__ import annotations


def evaluate_gate(review: dict, cfg: dict, dry_run: bool) -> dict:
    """质量门禁：决定当前文章能否进入发布/产物输出。返回 {allowed, action, reason, bypassed}。

    优先级：dry-run → 允许；门禁关闭 → disabled；有 blocker/高 fact/不放行/分数不足 → block；
    其余 → allow。
    """
    qg = cfg.get("article", {}).get("quality_gate", {})
    enabled = qg.get("enabled", True)
    min_score = float(qg.get("min_score", 70))
    block_high_fact = qg.get("block_on_high_fact_issue", True)

    if dry_run:
        return {"allowed": True, "action": "allow-dry-run", "reason": "dry-run 模式不拦截", "bypassed": True}
    if not enabled:
        return {"allowed": True, "action": "disabled", "reason": "质量门禁已关闭", "bypassed": True}

    score = float(review.get("overallScore", 0))
    allow = bool(review.get("allowPublish", False))
    action = review.get("recommendedAction", "revise")
    reasons: list[str] = []
    for issue in review.get("issues", []):
        if issue.get("severity") == "blocker":
            reasons.append(f"存在 blocker 级问题: {issue.get('message', '')}")
        if block_high_fact and issue.get("category") == "fact" and issue.get("severity") in ("high", "blocker"):
            reasons.append(f"高置信事实问题: {issue.get('message', '')}")
    if not allow:
        reasons.append("审稿判定不放行")
    elif action != "publish":
        reasons.append(f"推荐动作非 publish（{action}）")
    if score < min_score:
        reasons.append(f"综合分 {score:.0f} 低于门禁 {min_score}")

    if reasons:
        return {"allowed": False, "action": "block", "reason": "；".join(reasons), "bypassed": False}
    return {"allowed": True, "action": "allow", "reason": "通过质量门禁", "bypassed": False}


def should_revise(review: dict, max_rounds: int) -> bool:
    if max_rounds <= 0:
        return False
    if review.get("recommendedAction") == "publish" and review.get("overallScore", 0) >= 80:
        return False
    return any(_is_safe(i) for i in review.get("issues", []))


def _is_safe(issue: dict) -> bool:
    if issue.get("severity") == "blocker":
        return False
    if issue.get("autoFixable"):
        return True
    return issue.get("category") in {"title", "tone", "structure", "html"}


def safe_issues(review: dict) -> list[dict]:
    return [i for i in review.get("issues", []) if _is_safe(i)]