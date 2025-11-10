"""核心数据模型与JSON持久化工具."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class Record:
    """单条记账记录."""

    id: str
    amount: float
    category: str
    category_type: str  # income / expense
    date: dt.date

    def to_dict(self) -> Dict[str, str]:
        payload = asdict(self)
        payload["date"] = self.date.isoformat()
        return payload

    @staticmethod
    def from_dict(data: Dict[str, str]) -> "Record":
        return Record(
            id=data.get("id") or str(uuid.uuid4()),
            amount=float(data["amount"]),
            category=data["category"],
            category_type=data.get("category_type", "expense"),
            date=dt.date.fromisoformat(data["date"]),
        )


DEFAULT_CATEGORIES: Tuple[Tuple[str, str], ...] = (
    ("工资", "income"),
    ("理财收益", "income"),
    ("生活杂费", "expense"),
    ("餐饮", "expense"),
    ("交通", "expense"),
    ("娱乐", "expense"),
    ("学习", "expense"),
    ("医疗", "expense"),
)


class LedgerStore:
    """内存中的记录与分类仓库，并负责导入导出."""

    def __init__(self) -> None:
        self.records: List[Record] = []
        self.categories: Dict[str, str] = {}
        for name, ctype in DEFAULT_CATEGORIES:
            self.categories[name] = ctype

    def add_category(self, name: str, category_type: str) -> None:
        if not name:
            return
        self.categories[name] = category_type or "expense"

    def get_categories(self) -> List[Tuple[str, str]]:
        return sorted(self.categories.items())

    def add_record(
        self,
        amount: float,
        category: str,
        category_type: str,
        date: dt.date,
    ) -> Record:
        record = Record(
            id=str(uuid.uuid4()),
            amount=float(amount),
            category=category,
            category_type=category_type or self.categories.get(category, "expense"),
            date=date,
        )
        self.records.append(record)
        self.add_category(category, record.category_type)
        return record

    def update_record(
        self,
        record_id: str,
        amount: float,
        category: str,
        category_type: str,
        date: dt.date,
    ) -> Optional[Record]:
        record = self.find_record(record_id)
        if not record:
            return None
        record.amount = float(amount)
        record.category = category
        record.category_type = category_type or self.categories.get(category, "expense")
        record.date = date
        self.add_category(category, record.category_type)
        return record

    def delete_record(self, record_id: str) -> None:
        self.records = [r for r in self.records if r.id != record_id]

    def find_record(self, record_id: str) -> Optional[Record]:
        for record in self.records:
            if record.id == record_id:
                return record
        return None

    def search_records(
        self,
        start_date: Optional[dt.date] = None,
        end_date: Optional[dt.date] = None,
        category: Optional[str] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
    ) -> List[Record]:
        result: List[Record] = []
        for record in self.records:
            if start_date and record.date < start_date:
                continue
            if end_date and record.date > end_date:
                continue
            if category and record.category != category:
                continue
            if min_amount is not None and record.amount < min_amount:
                continue
            if max_amount is not None and record.amount > max_amount:
                continue
            result.append(record)
        return sorted(result, key=lambda r: r.date, reverse=True)

    def import_json(self, path: Path | str) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        categories = data.get("categories", [])
        self.categories.clear()
        for name, category_type in DEFAULT_CATEGORIES:
            self.categories[name] = category_type
        for item in categories:
            self.categories[item["name"]] = item.get("category_type", "expense")
        self.records = [Record.from_dict(item) for item in data.get("records", [])]

    def export_json(self, path: Path | str) -> None:
        payload = {
            "records": [record.to_dict() for record in self.records],
            "categories": [
                {"name": name, "category_type": category_type}
                for name, category_type in self.get_categories()
            ],
        }
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def monthly_trend(self, months: int = 6) -> List[Tuple[str, float]]:
        """返回最近N个月的净收支."""
        today = dt.date.today()
        base = dt.date(today.year, today.month, 1)
        buckets: Dict[str, float] = {}
        for i in range(months):
            year = base.year
            month = base.month - i
            while month <= 0:
                month += 12
                year -= 1
            key = f"{year:04d}-{month:02d}"
            buckets[key] = 0.0
        for record in self.records:
            key = record.date.strftime("%Y-%m")
            if key in buckets:
                sign = 1 if record.category_type == "income" else -1
                buckets[key] += record.amount * sign
        ordered = sorted(buckets.items())
        return ordered

    def current_month_breakdown(self, category_type: str = "expense") -> List[Tuple[str, float]]:
        today = dt.date.today()
        buckets: Dict[str, float] = {}
        for record in self.records:
            if record.date.year == today.year and record.date.month == today.month:
                if record.category_type != category_type:
                    continue
                buckets[record.category] = buckets.get(record.category, 0.0) + record.amount
        return sorted(buckets.items(), key=lambda item: item[1], reverse=True)

    def summary(self, start: Optional[dt.date] = None, end: Optional[dt.date] = None) -> Dict[str, float]:
        records = self.search_records(start, end)
        income = sum(r.amount for r in records if r.category_type == "income")
        expense = sum(r.amount for r in records if r.category_type == "expense")
        return {"income": income, "expense": expense, "balance": income - expense}
