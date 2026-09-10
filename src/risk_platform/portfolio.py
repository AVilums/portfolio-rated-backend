from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, Self
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)
from sqlalchemy import select

from risk_platform.auth import CurrentUser, Db
from risk_platform.models import Report

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


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


def analyse(request: PortfolioRequest) -> Analysis:
    """HHI uses entered weights; it cannot infer underlying fund holdings or risk."""
    weights = [p.allocation / 100 for p in request.positions]
    hhi = sum((w * w for w in weights), Decimal(0))
    largest = max(request.positions, key=lambda p: p.allocation)
    effective = (1 / hhi).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Analysis(
        concentration=float((hhi * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        effective_positions=float(effective),
        largest_allocation=float(largest.allocation),
        position_count=len(request.positions),
        observations=[
            f"{largest.ticker} is the largest position at {largest.allocation.normalize():f}%.",
            f"The allocation has the concentration of {effective:f} equally weighted positions.",
        ],
    )


def report_response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        created_at=report.created_at,
        positions=[Position.model_validate(p) for p in report.positions],
        analysis=Analysis.model_validate(report.analysis),
    )


@router.post("/analyse", response_model=ReportResponse, status_code=201)
def create_report(request: PortfolioRequest, user: CurrentUser, db: Db) -> ReportResponse:
    report = Report(
        user_id=user.id,
        positions=[p.model_dump(mode="json") for p in request.positions],
        analysis=analyse(request).model_dump(mode="json"),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report_response(report)


@router.get("/latest", response_model=ReportResponse | None)
def latest_report(user: CurrentUser, db: Db) -> ReportResponse | None:
    report = db.scalar(
        select(Report)
        .where(Report.user_id == user.id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(1)
    )
    return report_response(report) if report else None


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: UUID, user: CurrentUser, db: Db) -> ReportResponse:
    report = db.scalar(select(Report).where(Report.id == report_id, Report.user_id == user.id))
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report_response(report)
