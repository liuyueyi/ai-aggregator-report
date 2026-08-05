from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .dedup import fingerprint
from .fetchers.base import Signal


class StateStore:
    """幂等/跨日去重状态存储。

    seen.jsonl      每行 {"date","fingerprint","url","title"}：某日已产出到日报的信号指纹
    taglines.jsonl  每行 {"date","topic","tagline"}：每日各主题一句话摘要（跨日主题去重锚）

    .state 目录随 git 提交，保证 GitHub Actions 连续运行时跨日去重生效。
    """

    def __init__(self, state_dir: Path, window_days: int = 7,
                 seen_file: str = "seen.jsonl", taglines_file: str = "taglines.jsonl"):
        self.dir = Path(state_dir)
        self.window_days = window_days
        self.seen_path = self.dir / seen_file
        self.taglines_path = self.dir / taglines_file

    # ---------- seen ----------

    def seen_fingerprints(self, before_date: str) -> dict[str, str]:
        """返回 {fingerprint: date}，仅含窗口内且日期早于 before_date 的记录。

        before_date 传"今天"：今天已产出的记录不算跨日重复，
        —— 这样 --force 重跑当日时不会把所有信号都判为已见而产空日报。
        """
        if not self.seen_path.exists():
            return {}
        cutoff = datetime.strptime(before_date, "%Y-%m-%d").date() - timedelta(
            days=self.window_days
        )
        seen: dict[str, str] = {}
        for line in self.seen_path.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = rec.get("date", "")
            fp = rec.get("fingerprint", "")
            if not d or not fp:
                continue
            try:
                d_date = datetime.strptime(d, "%Y-%m-%d").date()
            except ValueError:
                continue
            if d_date < datetime.strptime(before_date, "%Y-%m-%d").date() and d_date >= cutoff:
                seen[fp] = d
        return seen

    def mark_seen(self, signals: list[Signal], today: str) -> list[Signal]:
        """为窗口内更早日期出现过指纹的信号设置 seen_on。"""
        seen = self.seen_fingerprints(today)
        if not seen:
            return signals
        for s in signals:
            fp = fingerprint(s)
            if fp in seen:
                s.seen_on = seen[fp]
        return signals

    def record_emitted(self, signals: list[Signal], date: str) -> int:
        """把本次已产出到日报的信号指纹 append 到 seen.jsonl（按指纹去重）。"""
        self.dir.mkdir(parents=True, exist_ok=True)
        existing: set[str] = set()
        if self.seen_path.exists():
            for line in self.seen_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    existing.add(json.loads(line).get("fingerprint", ""))
                except json.JSONDecodeError:
                    continue
        added = 0
        with self.seen_path.open("a", encoding="utf-8") as f:
            for s in signals:
                fp = fingerprint(s)
                if fp in existing:
                    continue
                rec = {"date": date, "fingerprint": fp, "url": s.url, "title": s.title}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                existing.add(fp)
                added += 1
        return added

    # ---------- taglines ----------

    def load_taglines(self, days: int = 7) -> list[dict]:
        """最近 N 天 {date, topic, tagline} 记录，作为日报生成时的跨日主题去重锚。"""
        if not self.taglines_path.exists():
            return []
        out: list[dict] = []
        for line in self.taglines_path.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out[-days:]

    def taglines_by_topic(self, days: int = 7) -> dict[str, list[str]]:
        by_topic: dict[str, list[str]] = {}
        for rec in self.load_taglines(days):
            topic = rec.get("topic", "")
            tagline = rec.get("tagline", "")
            if topic and tagline:
                by_topic.setdefault(topic, []).append(tagline)
        return by_topic

    def append_tagline(self, date: str, topic: str, tagline: str) -> None:
        if not tagline:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        rec = {"date": date, "topic": topic, "tagline": tagline}
        with self.taglines_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
