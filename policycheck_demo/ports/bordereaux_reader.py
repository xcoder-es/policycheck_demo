from __future__ import annotations

from typing import Protocol

from policycheck_demo.domain.validation.models import PolicyRecord


class BordereauxReader(Protocol):
    def read(self, content: bytes) -> tuple[list[PolicyRecord], list[str], list[str]]:
        """Return policy records, errors and warnings from uploaded bordereaux bytes."""
