from __future__ import annotations

from policycheck_demo.domain.bordereaux.models import Bordereaux
from policycheck_demo.domain.validation.models import PolicyRecord


def build_bordereaux(rows: list[PolicyRecord], source_label: str = "Portfolio bordereaux") -> Bordereaux:
    return Bordereaux(rows=rows, source_label=source_label)
