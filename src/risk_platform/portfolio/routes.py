from uuid import UUID

from fastapi import APIRouter, HTTPException

from risk_platform.auth.dependencies import CurrentUser
from risk_platform.database import Db
from risk_platform.portfolio.schemas import PortfolioRequest, ReportResponse
from risk_platform.portfolio.service import create_report, find_latest_report, find_report

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyse", response_model=ReportResponse, status_code=201)
def create(request: PortfolioRequest, user: CurrentUser, db: Db) -> ReportResponse:
    return create_report(db, user.id, request)


@router.get("/latest", response_model=ReportResponse | None)
def latest_report(user: CurrentUser, db: Db) -> ReportResponse | None:
    return find_latest_report(db, user.id)


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: UUID, user: CurrentUser, db: Db) -> ReportResponse:
    report = find_report(db, user.id, report_id)
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report
