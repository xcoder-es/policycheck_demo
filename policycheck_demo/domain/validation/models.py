from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ComplianceStatus(str, Enum):
    COMPLIANT = "Compliant"
    WARNING = "Warning"
    BREACH = "Breach"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AuthorityPeriod(BaseModel):
    start_date: date
    end_date: date


class BAARules(BaseModel):
    agreement_name: str = "Uploaded BAA"
    start_date: date
    end_date: date
    territories: list[str] = Field(default_factory=list)
    classes_of_business: list[str] = Field(default_factory=list)
    authority_limit: Decimal = Decimal("0")
    required_endorsements: list[str] = Field(default_factory=list)


class PolicyRecord(BaseModel):
    policy_number: str = "Policy"
    insured_name: str = "Unknown insured"
    bind_date: date | None = None
    territory: str = ""
    class_of_business: str = ""
    sum_insured: Decimal | None = None
    premium: Decimal | None = None
    endorsements: list[str] = Field(default_factory=list)
    broker: str = ""
    status: str = ""
    original_data: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    issue_type: str
    severity: Severity
    message: str


class ValidationResult(BaseModel):
    policy_number: str
    insured_name: str = "Unknown insured"
    status: ComplianceStatus
    severity: Severity
    issues: list[ValidationIssue] = Field(default_factory=list)
    issue_count: int = 0
    sum_insured: Decimal = Decimal("0")
    territory: str = ""
    class_of_business: str = ""
    bind_date: date | None = None
    original_data: dict[str, Any] = Field(default_factory=dict)


class PortfolioValidationSummary(BaseModel):
    total_policies: int = 0
    compliant_count: int = 0
    warning_count: int = 0
    breach_count: int = 0
    high_severity_count: int = 0
    total_exposure: Decimal = Decimal("0")
    exposure_outside_authority: Decimal = Decimal("0")
    most_common_issue: str = "None"
    compliance_percentage: float = 0.0


class ExceptionReport(BaseModel):
    rows: list[ValidationResult]
    checked_at: str
