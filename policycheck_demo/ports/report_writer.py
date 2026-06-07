from __future__ import annotations

from typing import Protocol

from policycheck_demo.domain.validation.models import ValidationResult


class ReportWriter(Protocol):
    def write_exception_report(self, results: list[ValidationResult]) -> str:
        """Return an exception report CSV string."""
