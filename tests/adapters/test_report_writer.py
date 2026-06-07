from __future__ import annotations

from datetime import date
from decimal import Decimal

from policycheck_demo.adapters.outbound.csv.csv_exception_report_writer import CsvExceptionReportWriter
from policycheck_demo.domain.validation.models import (
    ComplianceStatus,
    Severity,
    ValidationIssue,
    ValidationResult,
)


def test_exception_report_contains_validation_columns() -> None:
    result = ValidationResult(
        policy_number="PC-1",
        insured_name="A&B Holdings, Ltd",
        status=ComplianceStatus.BREACH,
        severity=Severity.HIGH,
        issues=[
            ValidationIssue(
                issue_type="Outside territory",
                severity=Severity.HIGH,
                message="Territory issue",
            )
        ],
        issue_count=1,
        sum_insured=Decimal("1200000"),
        territory="Canada",
        class_of_business="Cyber",
        bind_date=date(2026, 1, 1),
        original_data={
            "premium": "12000",
            "endorsements": "Sanctions Clause",
            "broker": "Marlow & Co",
        },
    )
    csv_text = CsvExceptionReportWriter().write_exception_report([result])
    assert "validation_status" in csv_text
    assert "severity" in csv_text
    assert "issues" in csv_text
    assert "issue_count" in csv_text
    assert "checked_at" in csv_text
    assert "A&B Holdings" in csv_text


def test_report_generation_handles_special_characters() -> None:
    result = ValidationResult(
        policy_number="PC-2",
        insured_name='Client "Quoted", Ltd',
        status=ComplianceStatus.WARNING,
        severity=Severity.MEDIUM,
        issues=[
            ValidationIssue(
                issue_type="Missing endorsement",
                severity=Severity.MEDIUM,
                message="Missing clause, review",
            )
        ],
        issue_count=1,
        sum_insured=Decimal("500000"),
        territory="United Kingdom",
        class_of_business="Cyber",
        bind_date=date(2026, 2, 2),
    )
    csv_text = CsvExceptionReportWriter().write_exception_report([result])
    assert 'Client ""Quoted"", Ltd' in csv_text
