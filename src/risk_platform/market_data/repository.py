import hashlib
import json
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from risk_platform.market_data.connectors import AlphaVantageConnector, EtfConnector
from risk_platform.market_data.models import EtfDataSnapshot
from risk_platform.market_data.schemas import EtfSnapshot, StoredSnapshot


def ingest(db: Session, connector: EtfConnector) -> list[UUID]:
    """Store a validated provider batch atomically; the caller owns the commit."""
    snapshots = [EtfSnapshot.model_validate(item.model_dump()) for item in connector.fetch()]
    ids: list[UUID] = []
    with db.begin_nested():
        for snapshot in snapshots:
            payload = snapshot.model_dump(mode="json")
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            identity = (
                EtfDataSnapshot.source == snapshot.source,
                EtfDataSnapshot.ticker == snapshot.ticker,
                EtfDataSnapshot.exchange == snapshot.exchange,
                EtfDataSnapshot.as_of == snapshot.as_of,
                EtfDataSnapshot.digest == digest,
            )
            statement = (
                insert(EtfDataSnapshot)
                .values(
                    id=uuid4(),
                    ticker=snapshot.ticker,
                    exchange=snapshot.exchange,
                    source=snapshot.source,
                    as_of=snapshot.as_of,
                    digest=digest,
                    payload=payload,
                )
                .on_conflict_do_nothing(constraint="uq_etf_snapshot_content")
                .returning(EtfDataSnapshot.id)
            )
            snapshot_id = db.scalar(statement)
            if snapshot_id is None:
                snapshot_id = db.scalars(select(EtfDataSnapshot.id).where(*identity)).one()
            ids.append(snapshot_id)
    return ids


def latest(db: Session, ticker: str, exchange: str, source: str) -> EtfDataSnapshot | None:
    return db.scalar(
        select(EtfDataSnapshot)
        .where(
            EtfDataSnapshot.ticker == ticker,
            EtfDataSnapshot.exchange == exchange,
            EtfDataSnapshot.source == source,
        )
        .order_by(
            EtfDataSnapshot.as_of.desc(),
            EtfDataSnapshot.ingested_at.desc(),
            EtfDataSnapshot.id.desc(),
        )
        .limit(1)
    )


def latest_for_ticker(db: Session, ticker: str) -> EtfDataSnapshot | None:
    return db.scalar(
        select(EtfDataSnapshot)
        .where(EtfDataSnapshot.ticker == ticker)
        .order_by(
            EtfDataSnapshot.as_of.desc(),
            (EtfDataSnapshot.source == AlphaVantageConnector.source).desc(),
            EtfDataSnapshot.ingested_at.desc(),
            EtfDataSnapshot.id.desc(),
        )
        .limit(1)
    )


def response(snapshot: EtfDataSnapshot) -> StoredSnapshot:
    data = EtfSnapshot.model_validate(snapshot.payload)
    coverage = (
        None
        if data.holdings is None
        else sum((holding.weight for holding in data.holdings), Decimal(0))
    )
    return StoredSnapshot(
        id=snapshot.id, ingested_at=snapshot.ingested_at, data=data, holdings_coverage=coverage
    )
