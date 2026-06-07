from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal

from .models import (
    BAARules,
    ComplianceStatus,
    PolicyRecord,
    PortfolioValidationSummary,
    Severity,
    ValidationIssue,
    ValidationResult,
)


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _has_endorsement(required: str, provided: list[str]) -> bool:
    required_norm = _normalise(required)
    return any(required_norm == _normalise(item) or required_norm in _normalise(item) for item in provided)


def validate_policy_against_baa(policy: PolicyRecord, baa: BAARules) -> ValidationResult:
    issues: list[ValidationIssue] = []

    if not policy.policy_number.strip():
        issues.append(
            ValidationIssue(
                issue_type="Missing policy number",
                severity=Severity.MEDIUM,
                message="Policy number is missing.",
            )
        )

    if policy.bind_date is None:
        issues.append(
            ValidationIssue(
                issue_type="Invalid bind date",
                severity=Severity.HIGH,
                message="Bind date is missing or malformed.",
            )
        )
    elif not (baa.start_date <= policy.bind_date <= baa.end_date):
        issues.append(
            ValidationIssue(
                issue_type="Outside BAA period",
                severity=Severity.HIGH,
                message=f"Bind date {policy.bind_date} is outside the reviewed BAA period.",
            )
        )

    allowed_territories = {_normalise(item) for item in baa.territories if item}
    if not policy.territory:
        issues.append(
            ValidationIssue(
                issue_type="Missing territory",
                severity=Severity.MEDIUM,
                message="Territory is missing.",
            )
        )
    elif allowed_territories and _normalise(policy.territory) not in allowed_territories:
        issues.append(
            ValidationIssue(
                issue_type="Outside territory",
                severity=Severity.HIGH,
                message=f"Territory '{policy.territory}' is not permitted by the BAA.",
            )
        )

    allowed_classes = {_normalise(item) for item in baa.classes_of_business if item}
    if not policy.class_of_business:
        issues.append(
            ValidationIssue(
                issue_type="Missing class",
                severity=Severity.MEDIUM,
                message="Class of business is missing.",
            )
        )
    elif allowed_classes and _normalise(policy.class_of_business) not in allowed_classes:
        issues.append(
            ValidationIssue(
                issue_type="Unsupported class",
                severity=Severity.HIGH,
                message=f"Class of business '{policy.class_of_business}' is not permitted by the BAA.",
            )
        )

    sum_insured = policy.sum_insured or Decimal("0")
    if policy.sum_insured is None:
        issues.append(
            ValidationIssue(
                issue_type="Invalid exposure",
                severity=Severity.MEDIUM,
                message="Sum insured is missing or malformed.",
            )
        )
    elif baa.authority_limit and sum_insured > baa.authority_limit:
        issues.append(
            ValidationIssue(
                issue_type="Above authority limit",
                severity=Severity.HIGH,
                message=(
                    f"Sum insured {sum_insured:,.0f} exceeds authority limit "
                    f"{baa.authority_limit:,.0f}."
                ),
            )
        )

    missing_endorsements = [
        endorsement
        for endorsement in baa.required_endorsements
        if endorsement and not _has_endorsement(endorsement, policy.endorsements)
    ]
    if missing_endorsements:
        issues.append(
            ValidationIssue(
                issue_type="Missing endorsement",
                severity=Severity.MEDIUM,
                message="Missing required endorsements: " + ", ".join(missing_endorsements) + ".",
            )
        )

    severity = Severity.LOW
    if any(issue.severity == Severity.HIGH for issue in issues):
        severity = Severity.HIGH
    elif any(issue.severity == Severity.MEDIUM for issue in issues):
        severity = Severity.MEDIUM

    if any(issue.severity == Severity.HIGH for issue in issues):
        status = ComplianceStatus.BREACH
    elif issues:
        status = ComplianceStatus.WARNING
    else:
        status = ComplianceStatus.COMPLIANT

    return ValidationResult(
        policy_number=policy.policy_number or "Unnumbered policy",
        insured_name=policy.insured_name,
        status=status,
        severity=severity,
        issues=issues,
        issue_count=len(issues),
        sum_insured=sum_insured,
        territory=policy.territory,
        class_of_business=policy.class_of_business,
        bind_date=policy.bind_date,
        original_data=policy.original_data,
    )


def build_portfolio_summary(results: list[ValidationResult]) -> PortfolioValidationSummary:
    total = len(results)
    compliant = sum(1 for item in results if item.status == ComplianceStatus.COMPLIANT)
    warnings = sum(1 for item in results if item.status == ComplianceStatus.WARNING)
    breaches = sum(1 for item in results if item.status == ComplianceStatus.BREACH)
    high = sum(1 for item in results for issue in item.issues if issue.severity == Severity.HIGH)
    exposure = sum((item.sum_insured for item in results), Decimal("0"))
    outside = sum(
        (item.sum_insured for item in results if any(i.issue_type == "Above authority limit" for i in item.issues)),
        Decimal("0"),
    )
    issue_counter = Counter(issue.issue_type for item in results for issue in item.issues)
    most_common = issue_counter.most_common(1)[0][0] if issue_counter else "None"
    percentage = round((compliant / total) * 100, 1) if total else 0.0
    return PortfolioValidationSummary(
        total_policies=total,
        compliant_count=compliant,
        warning_count=warnings,
        breach_count=breaches,
        high_severity_count=high,
        total_exposure=exposure,
        exposure_outside_authority=outside,
        most_common_issue=most_common,
        compliance_percentage=percentage,
    )
