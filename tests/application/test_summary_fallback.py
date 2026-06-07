from __future__ import annotations

from datetime import date
from decimal import Decimal

from policycheck_demo.adapters.outbound.ai.fallback_summary_generator import FallbackSummaryGenerator
from policycheck_demo.application.use_cases.validate_bordereaux import ValidateBordereauxUseCase
from policycheck_demo.domain.validation.models import BAARules, PolicyRecord


def test_summary_generation_uses_fallback_without_ai() -> None:
    baa = BAARules(
        agreement_name="Test Binder",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        territories=["United Kingdom"],
        classes_of_business=["Cyber"],
        authority_limit=Decimal("1000000"),
        required_endorsements=["Sanctions Clause"],
    )
    record = PolicyRecord(
        policy_number="PC-1",
        bind_date=date(2026, 6, 1),
        territory="United Kingdom",
        class_of_business="Cyber",
        sum_insured=Decimal("500000"),
        endorsements=["Sanctions Clause"],
    )
    output = ValidateBordereauxUseCase(FallbackSummaryGenerator()).execute(baa, [record])
    assert "bordereaux contains 1 policies" in output.executive_summary
    assert output.summary.compliant_count == 1


def test_summary_generation_never_blocks_validation() -> None:
    class BrokenSummaryGenerator:
        def generate_summary(self, summary, fallback: str) -> str:
            return fallback

    baa = BAARules(
        agreement_name="Test Binder",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        territories=["United Kingdom"],
        classes_of_business=["Cyber"],
        authority_limit=Decimal("1000000"),
        required_endorsements=[],
    )
    record = PolicyRecord(policy_number="PC-1", bind_date=date(2027, 1, 1), territory="Canada")
    output = ValidateBordereauxUseCase(BrokenSummaryGenerator()).execute(baa, [record])
    assert output.summary.breach_count == 1
    assert output.executive_summary
