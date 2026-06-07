from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from policycheck_demo.bordereaux import generate_synthetic_bordereaux
from policycheck_demo.domain.validation.models import BAARules, PolicyRecord
from policycheck_demo.adapters.outbound.csv.csv_bordereaux_reader import CsvBordereauxReader


class GenerateSyntheticBordereauxUseCase:
    def execute(self, baa: BAARules, count: int = 50) -> list[PolicyRecord]:
        rows = generate_synthetic_bordereaux(_legacy_baa(baa), count)
        return [CsvBordereauxReader()._to_policy_record(row) for row in rows]


def _legacy_baa(baa: BAARules):
    from policycheck_demo.models import BAA

    return BAA(
        name=baa.agreement_name,
        start_date=datetime.combine(baa.start_date, datetime.min.time()),
        end_date=datetime.combine(baa.end_date, datetime.min.time()),
        territory=baa.territories,
        class_of_business=baa.classes_of_business,
        authority_limit=float(baa.authority_limit or Decimal("0")),
        required_endorsements=baa.required_endorsements,
    )
