from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class BAARulesDTO(BaseModel):
    agreement_name: str = "Uploaded BAA"
    start_date: date
    end_date: date
    territories: list[str] = Field(default_factory=list)
    classes_of_business: list[str] = Field(default_factory=list)
    authority_limit: Decimal = Decimal("0")
    required_endorsements: list[str] = Field(default_factory=list)
