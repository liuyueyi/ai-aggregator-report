from __future__ import annotations

import json
import re
from pathlib import Path

from . import cover, decision, draft, evidence, gate, plan, rank, render, review, revision, title, topic
from .common import signal_to_item


def _slug(text: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text.strip()).strip("-")
    return (s or "article")[:50]


def _profile(cfg: dict) -> dict:
    profiles = (cfg.get("article") or {}).get("profiles") or {}
    if not profiles:
        return {"label": "综合观察", "audience": "信息读者", "tone": "客观", "preferred_topics": [], "title_format": "客观直述"}
    return next(iter(profiles.values()))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except (ValueError, OSError):
        return str(path)


def _used_item_ids(plan_result: dict) -> list[str]:
    ids: list[str] = []
    for sec in plan_result.get("sections", []):
        for it_id in sec.get("itemIds", []):
            if it_id not in ids:
                ids.append(it_id)
    for it_id in plan_result.get("sourceArticleIds", []):
        if it_id not in ids:
            ids.append(it_id)
    return ids


async def build_items(signals) -> list[dict]:
    return [signal_to_item(s, i) for i, s in enumerate(signals)] if signals else []


async def run_article(items: list[dict], cfg: dict, settings: dict, date: str,
                      prompts_dir: Path, output_dir: Path) -> dict:
    """执行一条文章生产工作流，返回产物路径 + 汇总。任一阶段失败走确定性兜底。"""
    if not items:
        return {"error": "no signals", "exit_code": 1}

    art_cfg = cfg.get("article", {})
    dry_run = art_cfg.get("dry_run", True)
    profile = _profile(cfg)
    qg = art_cfg.get("quality_gate", {})
    max_rounds = max(0, int(qg.get("max_revision_rounds", 1) or 1))

    # 1. 排序
    ranked = await rank.rank_items(items, settings)
    # 2. 选题聚类
    topic_report = await topic.create_topic_report(ranked, settings, prompts_dir, date, profile)
    # 3. 编辑决策
    decision_result = await decision.create_decision(topic_report, ranked, settings, prompts_dir, date, profile)
    # 4. 证据补全
    evidence_pack = await evidence.build_evidence_pack(topic_report, decision_result, ranked, cfg)
    # 5. 文章计划
    plan_result = await plan.create_plan(topic_report, decision_result, ranked, evidence_pack,
                                         settings, prompts_dir, date, profile)
    # 6. 草稿
    draft_md = await draft.draft_article(plan_result, ranked, evidence_pack, settings, prompts_dir)
    # 7. 标题
    final_title = title.pick_title(plan_result, decision_result, ranked)
    # 8. 审稿
    final_review = await review.review_article(final_title, draft_md, plan_result, ranked,
                                                evidence_pack, settings, prompts_dir, date)
    final_md = draft_md
    revision_summary = "未修复"

    # 9. 修订循环（单向，质量不降级才采纳）
    for round_no in range(1, max_rounds + 1):
        if not gate.should_revise(final_review, 1):
            break
        nt, nmd, applied = await revision.revise_article(
            final_title, final_md, plan_result, final_review, ranked, settings, prompts_dir
        )
        if not applied:
            revision_summary = f"第 {round_no} 轮无可自动修复项"
            break
        n_review = await review.review_article(nt, nmd, plan_result, ranked, evidence_pack,
                                               settings, prompts_dir, date)
        if revision.accept_revision(final_review, n_review):
            final_title, final_md, final_review = nt, nmd, n_review
            revision_summary = f"第 {round_no} 轮修复已采纳"
        else:
            revision_summary = f"第 {round_no} 轮修复未采纳，回滚"
            break

    # 10. 门禁
    gate_decision = gate.evaluate_gate(final_review, cfg, dry_run)
    # 11. 配图方案
    cover_plan = cover.build_cover_plan(plan_result, final_title, date)
    # 12. 排版
    md_text = render.build_markdown(final_title, plan_result, final_md, evidence_pack, date)
    html_text = render.markdown_to_wechat_html(md_text)

    slug = _slug(final_title)
    used_ids = _used_item_ids(plan_result)
    artifact = {
        "date": date, "title": final_title, "slug": slug, "dry_run": dry_run,
        "format": plan_result.get("format", ""), "thesis": plan_result.get("thesis", ""),
        "decision": decision_result, "topic_report": topic_report, "evidence": evidence_pack,
        "plan": plan_result, "review": final_review, "gate": gate_decision,
        "cover": cover_plan, "revision_summary": revision_summary,
        "used_item_ids": used_ids, "profile": profile.get("label", ""),
    }

    year, month, day = date.split("-")
    d = output_dir / year / month / day
    d.mkdir(parents=True, exist_ok=True)
    md_path = d / f"{slug}.md"
    html_path = d / f"{slug}.html"
    plan_path = d / f"{slug}.plan.json"
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    plan_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "exit_code": 0,
        "date": date,
        "mode": "mock" if settings.get("mock", False) else "llm",
        "title": final_title,
        "format": plan_result.get("format"),
        "gate_action": gate_decision.get("action"),
        "gate_reason": gate_decision.get("reason"),
        "overall_score": final_review.get("overallScore"),
        "revision": revision_summary,
        "cover_mode": "plan-only",
        "used_signals": len(used_ids),
        "used_item_ids": used_ids,
        "dir": _rel(d),
        "files": {"md": _rel(md_path), "html": _rel(html_path), "plan": _rel(plan_path)},
        "slug": slug,
    }