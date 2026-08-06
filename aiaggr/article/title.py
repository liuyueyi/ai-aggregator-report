from __future__ import annotations

import re

_LOW_QUALITY = re.compile(
    r"证据不足|史上首次|改写历史|夺回王座|杀回来了|炸裂|震撼|重磅|爆了|疯传|全网刷屏", re.I
)
_DATE_PREFIX = re.compile(r"^\d{4}[./-]\d{1,2}[./-]\d{1,2}\s*")
_BANNER = re.compile(r"^\s*(AI速递|AI早报|AI日报|早报|日报|速递)[|·:：\-]?\s*")
_SUFFIX = re.compile(r"\s*[|｜]\s*[^\s]+$")


def _normalize(title: str) -> str:
    t = title.strip().strip("「」『』「」\"'")
    t = _DATE_PREFIX.sub("", t)
    t = _BANNER.sub("", t)
    t = _SUFFIX.sub("", t)
    return t.strip()


def _is_low_quality(t: str) -> bool:
    return bool(_LOW_QUALITY.search(t))


def _truncate(t: str, max_len: int = 60) -> str:
    if len(t) <= max_len:
        return t
    cut = t[:max_len]
    for punct in "，。！？；,;!?；：":
        idx = cut.rfind(punct)
        if idx >= max_len * 0.6:
            cut = cut[: idx + 1]
            break
    return cut.rstrip()


def pick_title(plan: dict, decision: dict, items: list[dict]) -> str:
    """确定性标题：titleDirections → thesis → leadTopicTitle → 首个条目标题。"""
    item_map = {it["id"]: it for it in items}
    candidates: list[str] = []
    candidates.extend(d.get("title", "") for d in plan.get("titleDirections", []) if d.get("title"))
    if plan.get("thesis"):
        candidates.append(plan["thesis"])
    if decision.get("leadTopicTitle"):
        candidates.append(decision["leadTopicTitle"])
    if items:
        candidates.append(items[0]["title"])
    primary_id = plan.get("sections", [{}])[0].get("itemIds", [""])[0] if plan.get("sections") else ""
    if primary_id and primary_id in item_map:
        candidates.append(item_map[primary_id]["title"])

    chosen = ""
    for c in candidates:
        c = _normalize(c)
        if not c or _is_low_quality(c):
            continue
        chosen = _truncate(c)
        break
    if not chosen and items:
        chosen = _truncate(_normalize(items[0]["title"]))
    return chosen or _truncate(_normalize(plan.get("thesis", "今日观察")))