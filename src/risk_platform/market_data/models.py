from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from risk_platform.database import Base


class EtfDataSnapshot(Base):
    __tablename__ = "etf_data_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "source", "ticker", "exchange", "as_of", "digest", name="uq_etf_snapshot_content"
        ),
        Index("ix_etf_snapshot_lookup", "ticker", "exchange", "source", "as_of"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticker: Mapped[str] = mapped_column(String(40))
    exchange: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(100))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    digest: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, object]] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
