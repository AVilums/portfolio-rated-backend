from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from risk_platform.auth import CurrentUser
from risk_platform.database import Db
from risk_platform.models import Report
from risk_platform.portfolio.analysis import analyse
from risk_platform.portfolio.schemas import Analysis, PortfolioRequest, Position, ReportResponse

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


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
