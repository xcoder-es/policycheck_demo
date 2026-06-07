from __future__ import annotations

from datetime import date
from decimal import Decimal

from policycheck_demo.ai_utils import extract_fields_from_baa
from policycheck_demo.domain.validation.models import BAARules


def _as_date(value) -> date | None:
    if hasattr(value, "date"):
        return value.date()
    return None


class FallbackRuleExtractor:
    def extract_baa_rules(self, text: str, filename: str | None = None) -> BAARules:
        fields = extract_fields_from_baa(text)
        start_date = _as_date(fields.get("start_date")) or date.today()
        end_date = _as_date(fields.get("end_date")) or start_date
        return BAARules(
            agreement_name=str(fields.get("agreement_name") or filename or "Uploaded BAA"),
            start_date=start_date,
            end_date=end_date,
            territories=list(fields.get("territory") or []),
            classes_of_business=list(fields.get("class_of_business") or []),
            authority_limit=Decimal(str(fields.get("authority_limit") or "0")),
            required_endorsements=list(fields.get("required_endorsements") or []),
        )
