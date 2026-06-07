from __future__ import annotations

from policycheck_demo import pdf_utils


class PyPdfTextExtractor:
    def extract_text(self, content: bytes) -> str:
        return pdf_utils.extract_text_from_pdf_bytes(content)
