from __future__ import annotations

from policycheck_demo.domain.validation.models import BAARules, PolicyRecord, ValidationResult
from policycheck_demo.domain.validation.services import validate_policy_against_baa


class ValidateSinglePolicyUseCase:
    def execute(self, baa: BAARules, policy: PolicyRecord) -> ValidationResult:
        return validate_policy_against_baa(policy, baa)
