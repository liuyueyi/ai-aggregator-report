from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .dedup import fingerprint
from .fetchers.base import Signal


class StateStore:
    """幂等/跨日去重状态存储。

    seen.jsonl      每行 {"date","fingerprint","url","title"}：某日已产出到日报的信号指纹
    taglines.jsonl  每行 {"date","topic","tagline"}：每日各主题一句话摘要（跨日主题去重锚）

    .state 目录随 git 提交，保证 GitHub Actions 连续运行时跨日去重生效。

    归档机制：超过 window_days 天的记录自动归档到 .state/arch/YYYYMM-seen.jsonl，
    主 seen.jsonl 只保留最近 window_days 天的数据。
    """

    def __init__(self, state_dir: Path, window_days: int = 7,
                 seen_file: str = "seen.jsonl", taglines_file: str = "taglines.jsonl"):
        self.dir = Path(state_dir)
        self.window_days = window_days
        self.seen_path = self.dir / seen_file
        self.taglines_path = self.dir / taglines_file
        self.arch_dir = self.dir / "arch"

    # ---------- archive ----------

    def _get_archive_path(self, date_str: str) -> Path:
        """根据日期返回归档文件路径：.state/arch/YYYYMM-seen.jsonl"""
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            return self.arch_dir / f"{d.strftime('%Y%m')}-seen.jsonl"
        except ValueError:
            return self.arch_dir / "unknown-seen.jsonl"

    def _archive_old_records(self, today: str) -> int:
        """归档超过 window_days 天的记录，返回归档条数。

        读取 seen.jsonl，将旧记录追加到月度归档文件，
        然后重写 seen.jsonl 只保留最近 window_days 天的记录。
        """
        if not self.seen_path.exists():
            return 0

        today_date = datetime.strptime(today, "%Y-%m-%d").date()
        cutoff_date = today_date - timedelta(days=self.window_days)

        # 读取所有记录并分类
        keep_records: list[dict] = []
        archive_records: dict[str, list[dict]] = defaultdict(list)

        for line in self.seen_path.read_text(encoding="utf-8").strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = rec.get("date", "")
            if not d:
                keep_records.append(rec)
                continue
            try:
                rec_date = datetime.strptime(d, "%Y-%m-%d").date()
            except ValueError:
                keep_records.append(rec)
                continue
            if rec_date < cutoff_date:
                # 需要归档：按月份分组
                month_key = rec_date.strftime("%Y%m")
                archive_records[month_key].append(rec)
            else:
                # 保留：在窗口内
                keep_records.append(rec)

        # 无旧记录则跳过
        if not archive_records:
            return 0

        # 创建归档目录
        self.arch_dir.mkdir(parents=True, exist_ok=True)

        # 追加到月度归档文件
        archived_count = 0
        for month_key, records in archive_records.items():
            archive_path = self.arch_dir / f"{month_key}-seen.jsonl"
            with archive_path.open("a", encoding="utf-8") as f:
                for rec in records:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            archived_count += len(records)

        # 重写主文件（只保留最近 window_days 天）
        with self.seen_path.open("w", encoding="utf-8") as f:
            for rec in keep_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        return archived_count

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

    def record_emitted(self, signals: list[Signal], date: str) -> tuple[int, int]:
        """把本次已产出到日报的信号指纹 append 到 seen.jsonl（按指纹去重），并归档旧数据。

        返回 (新增指纹数, 归档指纹数)。
        """
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
        # 归档超过 window_days 天的旧记录
        archived = self._archive_old_records(date)
        return added, archived

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
