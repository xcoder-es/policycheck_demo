from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class ValidationIssueDTO(BaseModel):
    issue_type: str
    severity: str
    message: str


class ValidationResultDTO(BaseModel):
    policy_number: str
    status: str
    severity: str
    issues: list[ValidationIssueDTO] = Field(default_factory=list)
    issue_count: int = 0


class PortfolioValidationSummaryDTO(BaseModel):
    total_policies: int = 0
    compliant_count: int = 0
    warning_count: int = 0
    breach_count: int = 0
    high_severity_count: int = 0
    total_exposure: Decimal = Decimal("0")
    exposure_outside_authority: Decimal = Decimal("0")
    most_common_issue: str = "None"
    compliance_percentage: float = 0.0
