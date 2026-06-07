from __future__ import annotations

from policycheck_demo.ai_utils import generate_portfolio_summary
from policycheck_demo.domain.validation.models import PortfolioValidationSummary


class HuggingFaceSummaryGenerator:
    def generate_summary(self, summary: PortfolioValidationSummary, fallback: str) -> str:
        metrics = {
            "total_policies": summary.total_policies,
            "compliant_policies": summary.compliant_count,
            "warnings": summary.warning_count,
            "breaches": summary.breach_count,
            "high_severity_issues": summary.high_severity_count,
            "total_exposure_reviewed": float(summary.total_exposure),
            "exposure_outside_authority": float(summary.exposure_outside_authority),
            "most_common_issue": summary.most_common_issue,
            "percentage_compliant": summary.compliance_percentage,
        }
        return generate_portfolio_summary(metrics, fallback)
