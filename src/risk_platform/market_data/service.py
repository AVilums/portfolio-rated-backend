import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy.orm import Session

from risk_platform.config import get_settings
from risk_platform.market_data.connectors import (
    AlphaVantageConnector,
    ConnectorError,
    EtfListing,
    ProviderLimitError,
)
from risk_platform.market_data.models import EtfDataSnapshot
from risk_platform.market_data.repository import ingest, latest_for_ticker
from risk_platform.market_data.schemas import EtfSnapshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedEtfData:
    snapshot: EtfDataSnapshot | None
    status: str
    message: str


def resolve_for_report(
    db: Session, tickers: list[str], *, now: datetime | None = None
) -> dict[str, ResolvedEtfData]:
    """Use fresh stored data, refreshing stale/missing symbols while the provider works."""
    settings = get_settings()
    observed_at = now or datetime.now(UTC)
    maximum_age = timedelta(hours=settings.market_data_max_age_hours)
    secret = settings.alpha_vantage_api_key
    provider_blocked: str | None = None
    resolved: dict[str, ResolvedEtfData] = {}
    for ticker in tickers:
        stored = latest_for_ticker(db, ticker)
        fresh = stored is not None and observed_at - stored.as_of <= maximum_age
        if fresh:
            resolved[ticker] = ResolvedEtfData(stored, "available", "Stored ETF data is current.")
            continue
        refresh_error: str | None = None
        if secret is not None and secret.get_secret_value() and provider_blocked is None:
            existing = EtfSnapshot.model_validate(stored.payload) if stored else None
            listing = EtfListing(
                ticker=ticker,
                provider_symbol=existing.provider_symbol if existing else None,
                exchange=existing.exchange if existing else "UNKNOWN",
                currency=existing.currency if existing else "XXX",
                name=existing.name if existing else None,
            )
            try:
                ids = ingest(
                    db,
                    AlphaVantageConnector(secret.get_secret_value(), listing),
                )
                db.flush()
                stored = db.get(EtfDataSnapshot, ids[0])
                resolved[ticker] = ResolvedEtfData(
                    stored,
                    "available",
                    (
                        "ETF quote was refreshed; fund holdings are not available "
                        "from the provider."
                        if stored is not None
                        and EtfSnapshot.model_validate(stored.payload).holdings is None
                        else "ETF data was refreshed for this report."
                    ),
                )
                continue
            except ProviderLimitError as error:
                logger.warning("ETF provider limit while refreshing %s: %s", ticker, error)
                provider_blocked = "The live ETF data provider reached its request limit."
                refresh_error = provider_blocked
            except (ConnectorError, ValidationError) as error:
                logger.warning("ETF refresh failed for %s: %s", ticker, error)
                refresh_error = "The live ETF data provider could not refresh this ticker."
        if stored is not None:
            resolved[ticker] = ResolvedEtfData(
                stored,
                "stale",
                refresh_error
                or provider_blocked
                or (
                    "The latest stored ETF data is older than "
                    f"{settings.market_data_max_age_hours} hours."
                ),
            )
        else:
            resolved[ticker] = ResolvedEtfData(
                None,
                "unavailable",
                refresh_error
                or provider_blocked
                or "No stored ETF data is available and live data is not configured.",
            )
    return resolved
