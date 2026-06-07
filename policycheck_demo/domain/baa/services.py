from __future__ import annotations

from policycheck_demo.domain.validation.models import BAARules


def normalise_baa_rules(baa: BAARules) -> BAARules:
    return BAARules(
        agreement_name=baa.agreement_name.strip() or "Uploaded BAA",
        start_date=baa.start_date,
        end_date=baa.end_date,
        territories=[item.strip() for item in baa.territories if item.strip()],
        classes_of_business=[item.strip() for item in baa.classes_of_business if item.strip()],
        authority_limit=baa.authority_limit,
        required_endorsements=[item.strip() for item in baa.required_endorsements if item.strip()],
    )
