from __future__ import annotations

from policycheck_demo.adapters.outbound.ai.fallback_rule_extractor import FallbackRuleExtractor
from policycheck_demo.domain.validation.models import BAARules


class HuggingFaceRuleExtractor:
    """Facade kept behind a port; compliance still uses reviewed deterministic rules."""

    def __init__(self, fallback: FallbackRuleExtractor | None = None) -> None:
        self.fallback = fallback or FallbackRuleExtractor()

    def extract_baa_rules(self, text: str, filename: str | None = None) -> BAARules:
        return self.fallback.extract_baa_rules(text, filename)
