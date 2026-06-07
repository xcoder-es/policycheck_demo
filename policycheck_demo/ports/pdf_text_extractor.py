from __future__ import annotations

from typing import Protocol


class PdfTextExtractor(Protocol):
    def extract_text(self, content: bytes) -> str:
        """Extract text from a text-based PDF document."""
