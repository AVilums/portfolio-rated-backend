from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


class Position(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.:-]{0,19}$")
    allocation: Decimal = Field(gt=0, le=100, decimal_places=2, allow_inf_nan=False)

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_serializer("allocation")
    def serialize_allocation(self, value: Decimal) -> float:
        return float(value)


class PortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    positions: list[Position] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_portfolio(self) -> Self:
        if sum(p.allocation for p in self.positions) != Decimal("100"):
            raise ValueError("Allocations must total exactly 100%.")
        if len({p.ticker for p in self.positions}) != len(self.positions):
            raise ValueError("Asset symbols must be unique.")
        return self


class Analysis(BaseModel):
    method: Literal["allocation-v1"] = "allocation-v1"
    concentration: float
    effective_positions: float
    largest_allocation: float
    position_count: int
    observations: list[str]


class ReportResponse(BaseModel):
    id: UUID
    created_at: datetime
    positions: list[Position]
    analysis: Analysis
