from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from risk_platform.market_data.service import resolve_for_report
from risk_platform.portfolio.analysis import analyse
from risk_platform.portfolio.models import Report
from risk_platform.portfolio.schemas import Analysis, PortfolioRequest, Position, ReportResponse


def report_response(report: Report) -> ReportResponse:
    return ReportResponse(
        id=report.id,
        created_at=report.created_at,
        positions=[Position.model_validate(position) for position in report.positions],
        analysis=Analysis.model_validate(report.analysis),
    )


def create_report(db: Session, user_id: UUID, request: PortfolioRequest) -> ReportResponse:
    resolved = resolve_for_report(db, [position.ticker for position in request.positions])
    report = Report(
        user_id=user_id,
        positions=[position.model_dump(mode="json") for position in request.positions],
        analysis=analyse(request, resolved).model_dump(mode="json"),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report_response(report)


def find_latest_report(db: Session, user_id: UUID) -> ReportResponse | None:
    report = db.scalar(
        select(Report)
        .where(Report.user_id == user_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .limit(1)
    )
    return report_response(report) if report else None


def find_report(db: Session, user_id: UUID, report_id: UUID) -> ReportResponse | None:
    report = db.scalar(select(Report).where(Report.id == report_id, Report.user_id == user_id))
    return report_response(report) if report else None
