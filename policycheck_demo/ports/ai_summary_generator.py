from __future__ import annotations

from typing import Protocol

from policycheck_demo.domain.validation.models import PortfolioValidationSummary


class AiSummaryGenerator(Protocol):
    def generate_summary(self, summary: PortfolioValidationSummary, fallback: str) -> str:
        """Return an executive summary, or the provided fallback if unavailable."""
