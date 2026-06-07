from __future__ import annotations

import csv
import io
from datetime import datetime

from policycheck_demo.domain.validation.models import ValidationResult


class CsvExceptionReportWriter:
    def write_exception_report(self, results: list[ValidationResult]) -> str:
        checked_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        output = io.StringIO()
        fieldnames = [
            "policy_number",
            "insured_name",
            "bind_date",
            "territory",
            "class_of_business",
            "sum_insured",
            "premium",
            "endorsements",
            "broker",
            "status",
            "validation_status",
            "severity",
            "issues",
            "issue_count",
            "checked_at",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            source = result.original_data or {}
            writer.writerow(
                {
                    "policy_number": result.policy_number,
                    "insured_name": result.insured_name,
                    "bind_date": str(result.bind_date or source.get("bind_date", "")),
                    "territory": result.territory,
                    "class_of_business": result.class_of_business,
                    "sum_insured": str(result.sum_insured),
                    "premium": source.get("premium", ""),
                    "endorsements": source.get("endorsements", ""),
                    "broker": source.get("broker", ""),
                    "status": source.get("status", ""),
                    "validation_status": result.status.value,
                    "severity": result.severity.value,
                    "issues": "; ".join(issue.message for issue in result.issues),
                    "issue_count": result.issue_count,
                    "checked_at": checked_at,
                }
            )
        return output.getvalue()
