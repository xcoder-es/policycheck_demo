from __future__ import annotations

from pydantic import BaseModel, Field

from policycheck_demo.domain.validation.models import PolicyRecord


class Bordereaux(BaseModel):
    rows: list[PolicyRecord] = Field(default_factory=list)
    source_label: str = "Portfolio bordereaux"


BordereauxRow = PolicyRecord
