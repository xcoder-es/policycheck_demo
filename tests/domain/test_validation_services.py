from __future__ import annotations

from datetime import date
from decimal import Decimal

from policycheck_demo.domain.validation.models import BAARules, ComplianceStatus, PolicyRecord, Severity
from policycheck_demo.domain.validation.services import validate_policy_against_baa


def baa() -> BAARules:
    return BAARules(
        agreement_name="UK Cyber Binder",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        territories=["United Kingdom", "Ireland"],
        classes_of_business=["Cyber", "Professional Indemnity"],
        authority_limit=Decimal("2500000"),
        required_endorsements=["Sanctions Clause", "Cyber Incident Notification Clause"],
    )


def policy(**overrides) -> PolicyRecord:
    data = {
        "policy_number": "PC-001",
        "insured_name": "Northstar Logistics Ltd",
        "bind_date": date(2026, 6, 1),
        "territory": "United Kingdom",
        "class_of_business": "Cyber",
        "sum_insured": Decimal("1000000"),
        "endorsements": ["Sanctions Clause", "Cyber Incident Notification Clause"],
    }
    data.update(overrides)
    return PolicyRecord(**data)


def test_valid_policy_passes() -> None:
    result = validate_policy_against_baa(policy(), baa())
    assert result.status == ComplianceStatus.COMPLIANT
    assert result.severity == Severity.LOW
    assert result.issue_count == 0


def test_bind_date_before_baa_start_fails() -> None:
    result = validate_policy_against_baa(policy(bind_date=date(2025, 12, 31)), baa())
    assert result.status == ComplianceStatus.BREACH
    assert any(issue.issue_type == "Outside BAA period" for issue in result.issues)


def test_bind_date_after_baa_end_fails() -> None:
    result = validate_policy_against_baa(policy(bind_date=date(2027, 1, 1)), baa())
    assert result.status == ComplianceStatus.BREACH


def test_territory_outside_authority_fails() -> None:
    result = validate_policy_against_baa(policy(territory="United States"), baa())
    assert any(issue.issue_type == "Outside territory" for issue in result.issues)


def test_class_outside_authority_fails() -> None:
    result = validate_policy_against_baa(policy(class_of_business="Aviation"), baa())
    assert any(issue.issue_type == "Unsupported class" for issue in result.issues)


def test_sum_insured_above_authority_fails() -> None:
    result = validate_policy_against_baa(policy(sum_insured=Decimal("3000000")), baa())
    assert any(issue.issue_type == "Above authority limit" for issue in result.issues)


def test_missing_endorsement_fails() -> None:
    result = validate_policy_against_baa(policy(endorsements=["Sanctions Clause"]), baa())
    assert result.status == ComplianceStatus.WARNING
    assert any(issue.issue_type == "Missing endorsement" for issue in result.issues)


def test_multiple_breaches_on_one_policy() -> None:
    result = validate_policy_against_baa(
        policy(bind_date=date(2027, 1, 1), territory="Canada", sum_insured=Decimal("4000000")), baa()
    )
    assert result.status == ComplianceStatus.BREACH
    assert result.issue_count >= 3


def test_malformed_date_is_warning_or_breach() -> None:
    result = validate_policy_against_baa(policy(bind_date=None), baa())
    assert result.status == ComplianceStatus.BREACH
    assert any(issue.issue_type == "Invalid bind date" for issue in result.issues)


def test_malformed_sum_insured_is_warning() -> None:
    result = validate_policy_against_baa(policy(sum_insured=None), baa())
    assert result.status == ComplianceStatus.WARNING
    assert any(issue.issue_type == "Invalid exposure" for issue in result.issues)
