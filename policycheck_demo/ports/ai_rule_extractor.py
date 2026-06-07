from __future__ import annotations

from typing import Protocol

from policycheck_demo.domain.validation.models import BAARules


class AiRuleExtractor(Protocol):
    def extract_baa_rules(self, text: str, filename: str | None = None) -> BAARules:
        """Extract candidate BAA rules from text for human review."""
