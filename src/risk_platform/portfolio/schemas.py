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
    average_price: Decimal | None = Field(
        default=None, gt=0, max_digits=20, decimal_places=8, allow_inf_nan=False
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_serializer("allocation", "average_price")
    def serialize_decimal(self, value: Decimal | None) -> float | None:
        return float(value) if value is not None else None


class PortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    positions: list[Position] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_portfolio(self) -> Self:
        if any(p.average_price is None for p in self.positions):
            raise ValueError("Average price is required for every ETF.")
        if sum(p.allocation for p in self.positions) != Decimal("100"):
            raise ValueError("Allocations must total exactly 100%.")
        if len({p.ticker for p in self.positions}) != len(self.positions):
            raise ValueError("Asset symbols must be unique.")
        return self


class Analysis(BaseModel):
    method: Literal["allocation-v1", "etf-v1"] = "etf-v1"
    concentration: float
    effective_positions: float
    largest_allocation: float
    position_count: int
    observations: list[str]
    data_coverage: float = 0
    etfs: list["EtfAnalysis"] = Field(default_factory=list)
    underlying_exposure: list["UnderlyingExposure"] = Field(default_factory=list)


class AnalysedHolding(BaseModel):
    name: str
    fund_weight: float
    portfolio_exposure: float


class EtfAnalysis(BaseModel):
    ticker: str
    status: Literal["available", "stale", "unavailable"]
    message: str
    snapshot_id: UUID | None = None
    source: str | None = None
    as_of: datetime | None = None
    currency: str | None = None
    current_price: float | None = None
    price_change: float | None = None
    expense_ratio: float | None = None
    holdings_coverage: float | None = None
    top_holdings: list[AnalysedHolding] = Field(default_factory=list)


class UnderlyingExposure(BaseModel):
    name: str
    portfolio_exposure: float


class ReportResponse(BaseModel):
    id: UUID
    created_at: datetime
    positions: list[Position]
    analysis: Analysis
