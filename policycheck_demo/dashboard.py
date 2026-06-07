from __future__ import annotations

from collections import Counter
from typing import Any


def get_issue_type(issue: dict[str, Any]) -> str:
    return str(issue.get("type") or issue.get("issue_type") or "Unknown issue")


def get_issue_level(issue: dict[str, Any]) -> str:
    return str(issue.get("severity") or "low").lower()


def build_dashboard_data(rows: list[dict[str, Any]], metrics: dict[str, Any]) -> dict[str, Any]:
    total = int(metrics.get("total_policies") or len(rows) or 0)
    compliant = int(metrics.get("compliant_policies") or 0)
    warnings = int(metrics.get("warnings") or 0)
    breaches = int(metrics.get("breaches") or 0)
    issue_counter: Counter[str] = Counter()
    level_counter: Counter[str] = Counter({"low": 0, "medium": 0, "high": 0})
    affected_counter: Counter[str] = Counter()
    high_exposure = 0.0

    for item in rows:
        issues = item.get("issues") or []
        seen: set[str] = set()
        for issue in issues:
            issue_type = get_issue_type(issue)
            level = get_issue_level(issue)
            issue_counter[issue_type] += 1
            if level in level_counter:
                level_counter[level] += 1
            seen.add(issue_type)
        for issue_type in seen:
            affected_counter[issue_type] += 1
        if any(get_issue_level(issue) == "high" for issue in issues):
            high_exposure += float(item.get("sum_insured_value") or 0)

    issue_categories = [
        {"type": issue_type, "count": count, "affected_policies": affected_counter[issue_type]}
        for issue_type, count in issue_counter.most_common()
    ]
    most_common = issue_categories[0] if issue_categories else {"type": "None", "count": 0, "affected_policies": 0}
    affected = int(most_common.get("affected_policies") or 0)
    affected_percent = round((affected / total) * 100, 1) if total else 0.0

    def percentage(value: int) -> float:
        return round((value / total) * 100, 1) if total else 0.0

    return {
        "compliance_breakdown": [
            {"label": "Compliant", "count": compliant, "percentage": percentage(compliant)},
            {"label": "Warnings", "count": warnings, "percentage": percentage(warnings)},
            {"label": "Breaches", "count": breaches, "percentage": percentage(breaches)},
        ],
        "issue_categories": issue_categories,
        "exposure_metrics": [
            {"label": "Total exposure reviewed", "value": float(metrics.get("total_exposure_reviewed") or 0)},
            {"label": "Exposure outside authority", "value": float(metrics.get("exposure_outside_authority") or 0)},
            {"label": "High severity exposure", "value": high_exposure},
        ],
        "severity_distribution": [
            {"label": "Low", "count": int(level_counter["low"])},
            {"label": "Medium", "count": int(level_counter["medium"])},
            {"label": "High", "count": int(level_counter["high"])},
        ],
        "common_issue_insight": {
            "type": most_common["type"],
            "affected_policies": affected,
            "portfolio_percentage": affected_percent,
            "text": f"{most_common['type']} appears in {affected} policies, representing {affected_percent}% of the reviewed portfolio.",
        },
    }
