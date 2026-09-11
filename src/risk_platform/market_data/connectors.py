import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from risk_platform.market_data.schemas import EtfSnapshot, Holding, Quote

ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
JsonObject = dict[str, object]
HttpGet = Callable[[str, float], bytes]


class ConnectorError(RuntimeError):
    """A market-data provider could not produce a valid snapshot."""


class ProviderLimitError(ConnectorError):
    """A provider rejected the request because its usage limit was reached."""


class EtfListing(BaseModel):
    """Listing facts Alpha Vantage does not return from ETF_PROFILE."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    ticker: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.:-]{0,39}$")
    exchange: str = Field(pattern=r"^[A-Z0-9][A-Z0-9.:-]{0,39}$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    name: str | None = Field(default=None, min_length=1, max_length=300)


class EtfConnector(Protocol):
    """Adapters translate source data into validated, source-attributed ETF snapshots."""

    def fetch(self) -> list[EtfSnapshot]: ...


class JsonFileConnector:
    """Import a UTF-8 JSON array exported into our documented interchange format."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def fetch(self) -> list[EtfSnapshot]:
        return TypeAdapter(list[EtfSnapshot]).validate_json(self.path.read_text(encoding="utf-8"))


def _http_get(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "PortfolioRated/0.2"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed HTTPS host
            return cast(bytes, response.read())
    except (HTTPError, URLError, TimeoutError) as error:
        raise ConnectorError("Alpha Vantage request failed.") from error


class AlphaVantageConnector:
    """Fetch one ETF profile and closing quote using a free Alpha Vantage API key."""

    source = "alpha-vantage"

    def __init__(
        self,
        api_key: str,
        listing: EtfListing,
        *,
        timeout: float = 10,
        http_get: HttpGet = _http_get,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not api_key.strip():
            raise ValueError("Alpha Vantage API key is required.")
        if timeout <= 0:
            raise ValueError("Timeout must be positive.")
        self.api_key = api_key.strip()
        self.listing = listing
        self.timeout = timeout
        self.http_get = http_get
        self.clock = clock

    def fetch(self) -> list[EtfSnapshot]:
        fetched_at = self.clock()
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            raise ConnectorError("Connector clock must return a timezone-aware timestamp.")
        profile = self._request("ETF_PROFILE")
        quote_data = self._request("GLOBAL_QUOTE")
        quote = self._parse_quote(quote_data)
        holdings = self._parse_holdings(profile)
        expense_ratio = self._optional_decimal(profile, "net_expense_ratio")
        return [
            EtfSnapshot(
                ticker=self.listing.ticker,
                exchange=self.listing.exchange,
                currency=self.listing.currency,
                name=self.listing.name or self.listing.ticker,
                source=self.source,
                as_of=fetched_at,
                expense_ratio=expense_ratio,
                quote=quote,
                holdings=holdings,
                # ETF_PROFILE has no composition date; record when we observed it.
                holdings_as_of=fetched_at,
            )
        ]

    def _request(self, function: str) -> JsonObject:
        query = urlencode(
            {"function": function, "symbol": self.listing.ticker, "apikey": self.api_key}
        )
        try:
            value = json.loads(self.http_get(f"{ALPHA_VANTAGE_URL}?{query}", self.timeout))
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise ConnectorError("Alpha Vantage returned invalid JSON.") from error
        if not isinstance(value, dict):
            raise ConnectorError("Alpha Vantage returned an unexpected response.")
        data: JsonObject = value
        if "Note" in data or "Information" in data:
            raise ProviderLimitError("Alpha Vantage rejected the request or reached its API limit.")
        if "Error Message" in data:
            raise ConnectorError("Alpha Vantage did not recognize the ETF symbol.")
        return data

    def _parse_quote(self, response: JsonObject) -> Quote:
        raw = response.get("Global Quote")
        if not isinstance(raw, dict):
            raise ConnectorError("Alpha Vantage returned no quote for the ETF.")
        try:
            price = Decimal(str(raw["05. price"]))
            quote_date = datetime.strptime(str(raw["07. latest trading day"]), "%Y-%m-%d").replace(
                tzinfo=UTC
            )
        except (KeyError, InvalidOperation, ValueError) as error:
            raise ConnectorError("Alpha Vantage returned an invalid ETF quote.") from error
        return Quote(price=price, as_of=quote_date)

    def _parse_holdings(self, profile: JsonObject) -> list[Holding]:
        raw_holdings = profile.get("holdings")
        if not isinstance(raw_holdings, list):
            raise ConnectorError("Alpha Vantage returned no ETF holdings.")
        holdings: list[Holding] = []
        identifiers: set[str] = set()
        for index, raw in enumerate(raw_holdings):
            if not isinstance(raw, dict):
                raise ConnectorError("Alpha Vantage returned invalid ETF holdings.")
            try:
                symbol = str(raw.get("symbol") or "").strip().upper()
                name = str(raw["description"]).strip()
                weight = Decimal(str(raw["weight"]))
            except (KeyError, InvalidOperation) as error:
                raise ConnectorError("Alpha Vantage returned invalid ETF holdings.") from error
            base = f"alpha-vantage:{symbol or name.casefold()}"
            identifier = base if base not in identifiers else f"{base}:{index}"
            identifiers.add(identifier)
            holdings.append(Holding(identifier=identifier, name=name, weight=weight))
        return holdings

    @staticmethod
    def _optional_decimal(profile: JsonObject, key: str) -> Decimal | None:
        value = profile.get(key)
        if value in (None, "", "None"):
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation as error:
            raise ConnectorError(f"Alpha Vantage returned an invalid {key}.") from error
