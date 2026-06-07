from __future__ import annotations

from policycheck_demo.domain.validation.models import PortfolioValidationSummary


class FallbackSummaryGenerator:
    def generate_summary(self, summary: PortfolioValidationSummary, fallback: str) -> str:
        return fallback


def build_local_summary(summary: PortfolioValidationSummary) -> str:
    return (
        f"The bordereaux contains {summary.total_policies} policies. "
        f"{summary.compliant_count} policies are compliant, with "
        f"{summary.warning_count} warnings and {summary.breach_count} breaches. "
        f"The most common exception pattern is {summary.most_common_issue}."
    )
