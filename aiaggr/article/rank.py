from __future__ import annotations

from ..llm import call_text, is_mock

_RANK_SYSTEM = (
    "你是内容排序引擎。请按给定评分口径对这些候选内容打分（0-100，一位小数），"
    "一行一条，格式严格为：文章ID: 分数。分数要有区分度，无需任何解释。"
)


def _local_score(score: float, heat: str, age_bucket: str, content_len: int) -> float:
    base = 40 + float(score) * 35
    try:
        heat_num = float(str(heat).replace(",", "").replace("万", "e4").replace("亿", "e8"))
    except (TypeError, ValueError):
        heat_num = 0.0
    if heat_num > 0:
        if heat_num >= 1_000_000:
            base += 12
        elif heat_num >= 100_000:
            base += 8
        else:
            base += 4
    base += {"today": 12, "today_window": 12, "past_72h": 7, "older": 1, "unknown": 3}.get(age_bucket, 3)
    if content_len >= 400:
        base += 8
    elif content_len >= 150:
        base += 4
    elif content_len == 0:
        base -= 5
    return max(0.0, min(base, 100.0))


def rank_items_local(items: list[dict]) -> list[dict]:
    out = []
    for it in items:
        ranked = dict(it)
        ranked["_rank"] = _local_score(
            it.get("score", 0),
            it.get("heat", ""),
            it.get("age_bucket", "unknown"),
            len(it.get("content", "")),
        )
        out.append(ranked)
    out.sort(key=lambda x: x["_rank"], reverse=True)
    return out


def _parse_rank_text(text: str) -> dict[str, float]:
    import re

    scores: dict[str, float] = {}
    for line in text.splitlines():
        m = re.match(r"^(c\d+)[\s:：]+(\d+(?:\.\d+)?)$", line.strip())
        if not m:
            m = re.search(r"(c\d+)[\s:：]+(\d+(?:\.\d+)?)", line)
        if m:
            try:
                scores[m.group(1)] = float(m.group(2))
            except ValueError:
                continue
    return scores


async def rank_items(items: list[dict], settings: dict) -> list[dict]:
    """排序：LLM 打分优先，失败走确定性排序。返回按 _rank 降序的 items。"""
    if is_mock(settings) or not items:
        return rank_items_local(items)
    lines = "\n".join(f"{it['id']} / {it['title']} / 热度:{it.get('heat','')} / 摘要:{it['summary'][:120]}" for it in items)
    user = (
        "评分标准：新信息密度与时效 25 / 影响范围与行业信号 25 / 实用性与可操作性 20 / "
        "可信度与内容质量 20 / 表达素材价值 10。单个并列内容只保留信息量最高的一篇。\n"
        f"候选：\n{lines}"
    )
    plain_scores: dict[str, float] = {}
    try:
        text = call_text(_RANK_SYSTEM, user, settings, temperature=0.2)
    except Exception as e:  # noqa: BLE001
        print(f"[article:rank] LLM failed, fallback local: {e}")
        return rank_items_local(items)
    plain_scores = _parse_rank_text(text)
    if not plain_scores:
        return rank_items_local(items)
    out = []
    for it in items:
        out.append({
            **it,
            "_rank": plain_scores.get(it["id"], 0.0),
        })
    out.sort(key=lambda x: x["_rank"], reverse=True)
    return out