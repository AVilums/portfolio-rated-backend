from uuid import UUID

from fastapi import APIRouter, HTTPException

from risk_platform.auth import CurrentUser
from risk_platform.database import Db
from risk_platform.market_data.models import EtfDataSnapshot
from risk_platform.market_data.schemas import StoredSnapshot
from risk_platform.market_data.service import latest, response

router = APIRouter(prefix="/market-data/etfs", tags=["ETF market data"])


@router.get("/latest", response_model=StoredSnapshot)
def latest_etf(
    ticker: str, exchange: str, source: str, user: CurrentUser, db: Db
) -> StoredSnapshot:
    snapshot = latest(db, ticker.strip().upper(), exchange.strip().upper(), source.strip().lower())
    if snapshot is None:
        raise HTTPException(404, "ETF data not found.")
    return response(snapshot)


@router.get("/snapshots/{snapshot_id}", response_model=StoredSnapshot)
def get_snapshot(snapshot_id: UUID, user: CurrentUser, db: Db) -> StoredSnapshot:
    snapshot = db.get(EtfDataSnapshot, snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "ETF data not found.")
    return response(snapshot)
