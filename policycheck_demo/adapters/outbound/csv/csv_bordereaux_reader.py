from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from policycheck_demo.bordereaux import parse_bordereaux_csv, split_values
from policycheck_demo.domain.validation.models import PolicyRecord


def _parse_date(value: str):
    value = (value or "").strip().replace(",", "")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> Decimal | None:
    cleaned = "".join(ch for ch in (value or "") if ch.isdigit() or ch in ".-")
    if not cleaned or cleaned in {".", "-"}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


class CsvBordereauxReader:
    def read(self, content: bytes) -> tuple[list[PolicyRecord], list[str], list[str]]:
        parsed = parse_bordereaux_csv(content)
        records = [self._to_policy_record(row) for row in parsed.rows]
        return records, parsed.errors, parsed.warnings

    def _to_policy_record(self, row: dict[str, Any]) -> PolicyRecord:
        return PolicyRecord(
            policy_number=str(row.get("policy_number") or ""),
            insured_name=str(row.get("insured_name") or "Unknown insured"),
            bind_date=_parse_date(str(row.get("bind_date") or "")),
            territory=str(row.get("territory") or ""),
            class_of_business=str(row.get("class_of_business") or ""),
            sum_insured=_parse_decimal(str(row.get("sum_insured") or "")),
            premium=_parse_decimal(str(row.get("premium") or "")),
            endorsements=split_values(str(row.get("endorsements") or "")),
            broker=str(row.get("broker") or ""),
            status=str(row.get("status") or ""),
            original_data={key: str(value or "") for key, value in row.items()},
        )
