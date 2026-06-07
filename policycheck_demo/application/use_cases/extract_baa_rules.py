from __future__ import annotations

from policycheck_demo.domain.validation.models import BAARules
from policycheck_demo.ports.ai_rule_extractor import AiRuleExtractor
from policycheck_demo.ports.pdf_text_extractor import PdfTextExtractor


class ExtractBAARulesUseCase:
    def __init__(self, pdf_extractor: PdfTextExtractor, rule_extractor: AiRuleExtractor) -> None:
        self.pdf_extractor = pdf_extractor
        self.rule_extractor = rule_extractor

    def from_text(self, text: str, filename: str | None = None) -> BAARules:
        return self.rule_extractor.extract_baa_rules(text, filename)

    def from_pdf(self, content: bytes, filename: str | None = None) -> BAARules:
        text = self.pdf_extractor.extract_text(content)
        return self.from_text(text, filename)
