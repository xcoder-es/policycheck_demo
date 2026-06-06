"""
checker.py
-----------

This module contains functions that perform validation checks on
policies bound under a Binding Authority Agreement (BAA).  It is
separate from the AI extraction logic so that the core business rules
are clear and testable independently of any language model.
"""

from datetime import datetime
from typing import Dict, List

from .models import BAA, Policy


def check_policy_against_baa(policy: Policy, baa: BAA) -> List[str]:
    """Check a policy against BAA terms.

    Returns a list of human‑readable issue messages.  If the list is
    empty then the policy meets all BAA constraints.
    """
    issues: List[str] = []
    # date range
    if not (baa.start_date <= policy.bind_date <= baa.end_date):
        issues.append(
            f"Bind date {policy.bind_date.date()} is outside BAA period "
            f"({baa.start_date.date()}–{baa.end_date.date()})."
        )
    # territory
    if policy.territory not in baa.territory:
        allowed = ", ".join(baa.territory)
        issues.append(
            f"Territory “{policy.territory}” is not permitted (allowed: {allowed})."
        )
    # class of business
    if policy.class_of_business not in baa.class_of_business:
        allowed_classes = ", ".join(baa.class_of_business)
        issues.append(
            f"Class of business “{policy.class_of_business}” is not permitted "
            f"(allowed: {allowed_classes})."
        )
    # authority limit
    if policy.sum_insured > baa.authority_limit:
        issues.append(
            f"Sum insured {policy.sum_insured:,.0f} exceeds authority limit {baa.authority_limit:,.0f}."
        )
    # endorsements
    missing = [e for e in baa.required_endorsements if e not in policy.endorsements]
    if missing:
        issues.append(f"Missing required endorsements: {', '.join(missing)}.")
    return issues


def check_bordereau_delays(
    policy: Policy, bordereau: Dict[str, datetime], grace_period_days: int = 14
) -> List[str]:
    """Check the reporting delay for a policy.

    The `bordereau` mapping should map each policy number to the date
    it was reported to the managing agent.  Any record missing from
    the bordereau or reported later than `grace_period_days` after the
    bind date will produce a human‑readable issue message.
    """
    issues: List[str] = []
    report_date = bordereau.get(policy.policy_number)
    if report_date is None:
        issues.append("Policy is missing from bordereau.")
    else:
        delay_days = (report_date - policy.bind_date).days
        if delay_days > grace_period_days:
            issues.append(
                f"Bordereau delay: reported {delay_days} days after bind date (grace period {grace_period_days} days)."
            )
    return issues