from __future__ import annotations

import json

from .config import promp_dir
from .fetchers.base import Signal
from .llm import call_json, is_mock

SYSTEM = "你是精准的新闻信号主题分类器。严格输出 JSON，不要解释。"


def rule_assign(signals: list[Signal], topics_cfg: dict[str, dict]) -> None:
    """规则分配：按源白名单 + 抓取器预分配（user OPML）填充 signal.topics。"""
    for s in signals:
        assigned: set[str] = set()
        for tkey, tconf in topics_cfg.items():
            if s.source_key in tconf.get("sources", []):
                assigned.add(tkey)
        for t in s.topics:
            if t in topics_cfg:
                assigned.add(t)
        s.topics = sorted(assigned)


def _llm_refine(signals: list[Signal], topics_cfg: dict[str, dict], settings: dict) -> None:
    """LLM 精修：HN/GitHub 等通用源可能命中规则之外的更深层主题。失败时忽略。"""
    topics_desc = "\n".join(f"- {k}: {v.get('name')}" for k, v in topics_cfg.items())
    signals_json = json.dumps(
        [
            {
                "id": i,
                "source": s.source,
                "title": s.title,
                "summary": (s.summary or "")[:200],
                "tags": s.tags,
            }
            for i, s in enumerate(signals)
        ],
        ensure_ascii=False,
        indent=1,
    )
    user = (
        (promp_dir({}) / "classifier.md")
        .read_text(encoding="utf-8")
        .replace("{{topics_desc}}", topics_desc)
        .replace("{{signals_json}}", signals_json)
    )
    try:
        result = call_json(SYSTEM, user, settings, temperature=0.2)
    except Exception as err:
        print(f"[classifier] llm refine failed, keep rule result: {err}")
        return

    assignments = result.get("assignments", []) if isinstance(result, dict) else []
    for item in assignments:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(signals)):
            continue
        topics = item.get("topics", [])
        valid = [t for t in topics if t in topics_cfg]
        if valid:
            signals[idx].topics = sorted(set(signals[idx].topics) | set(valid))


def classify(
    signals: list[Signal],
    topics_cfg: dict[str, dict],
    settings: dict,
    *,
    use_llm: bool = True,
) -> dict[str, list[Signal]]:
    """把信号分配到各主题。返回 {topic_key: [signals]}。

    基础分配 = 规则（源白名单 + 预分配）；use_llm 时用 LLM 精修（失败自动降级）。
    """
    rule_assign(signals, topics_cfg)
    if use_llm and not is_mock(settings) and signals:
        _llm_refine(signals, topics_cfg, settings)

    pools: dict[str, list[Signal]] = {k: [] for k in topics_cfg}
    for s in signals:
        for t in s.topics:
            if t in pools:
                pools[t].append(s)
    return pools