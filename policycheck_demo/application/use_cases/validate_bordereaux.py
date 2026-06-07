from __future__ import annotations

from dataclasses import dataclass

from policycheck_demo.adapters.outbound.ai.fallback_summary_generator import build_local_summary
from policycheck_demo.domain.validation.models import (
    BAARules,
    PolicyRecord,
    PortfolioValidationSummary,
    ValidationResult,
)
from policycheck_demo.domain.validation.services import build_portfolio_summary, validate_policy_against_baa
from policycheck_demo.ports.ai_summary_generator import AiSummaryGenerator


@dataclass
class BordereauxValidationOutput:
    results: list[ValidationResult]
    summary: PortfolioValidationSummary
    executive_summary: str


class ValidateBordereauxUseCase:
    def __init__(self, summary_generator: AiSummaryGenerator) -> None:
        self.summary_generator = summary_generator

    def execute(self, baa: BAARules, records: list[PolicyRecord]) -> BordereauxValidationOutput:
        results = [validate_policy_against_baa(record, baa) for record in records]
        summary = build_portfolio_summary(results)
        fallback = build_local_summary(summary)
        executive = self.summary_generator.generate_summary(summary, fallback)
        return BordereauxValidationOutput(results=results, summary=summary, executive_summary=executive)
