from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class BordereauxRowDTO(BaseModel):
    policy_number: str = ""
    insured_name: str = "Unknown insured"
    bind_date: date | None = None
    territory: str = ""
    class_of_business: str = ""
    sum_insured: Decimal | None = None
    premium: Decimal | None = None
    endorsements: list[str] = Field(default_factory=list)
    broker: str = ""
    status: str = ""


class BordereauxDTO(BaseModel):
    rows: list[BordereauxRowDTO] = Field(default_factory=list)
    source_label: str = "Uploaded bordereaux"
