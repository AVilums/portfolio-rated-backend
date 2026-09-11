import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from pydantic import ValidationError

from risk_platform.market_data.connectors import (
    AlphaVantageConnector,
    ConnectorError,
    EtfListing,
    JsonFileConnector,
    ProviderLimitError,
)
from risk_platform.market_data.schemas import EtfSnapshot


def sample() -> dict[str, object]:
    return {
        "ticker": "TEST",
        "exchange": "XNAS",
        "currency": "USD",
        "name": "Synthetic ETF",
        "source": "fixture",
        "as_of": "2026-09-10T20:00:00Z",
        "quote": {"price": "123.45", "as_of": "2026-09-10T19:00:00Z"},
        "holdings": [{"identifier": "example", "name": "Example holding", "weight": "65.2"}],
        "holdings_as_of": "2026-09-09T20:00:00Z",
    }


def test_file_connector_preserves_partial_holdings_and_decimal_price(tmp_path: Path) -> None:
    path = tmp_path / "etfs.json"
    path.write_text(json.dumps([sample()]), encoding="utf-8")
    snapshot = JsonFileConnector(path).fetch()[0]
    assert snapshot.quote is not None
    assert str(snapshot.quote.price) == "123.45"
    assert snapshot.holdings is not None
    assert str(snapshot.holdings[0].weight) == "65.2"


@pytest.mark.parametrize(
    "patch",
    [
        {"instrument_type": "STOCK"},
        {"currency": "usd"},
        {"as_of": "2026-09-10T20:00:00"},
        {"holdings_as_of": None},
        {"quote": {"price": "NaN", "as_of": "2026-09-10T19:00:00Z"}},
        {"quote": {"price": "0", "as_of": "2026-09-10T19:00:00Z"}},
        {"quote": {"price": "100", "as_of": "2026-09-11T19:00:00Z"}},
        {"expense_ratio": "-1"},
        {"holdings": [{"identifier": "a", "name": "A", "weight": 101}]},
        {
            "holdings": [
                {"identifier": "a", "name": "A", "weight": 60},
                {"identifier": "b", "name": "B", "weight": 60},
            ]
        },
        {
            "holdings": [
                {"identifier": "a", "name": "A", "weight": 10},
                {"identifier": "a", "name": "A", "weight": 10},
            ]
        },
    ],
)
def test_invalid_snapshots(patch: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        EtfSnapshot.model_validate(sample() | patch)


def test_missing_holdings_are_distinct_from_empty_holdings() -> None:
    snapshot = EtfSnapshot.model_validate(sample() | {"holdings": None, "holdings_as_of": None})
    assert snapshot.holdings is None


def test_file_connector_rejects_entire_invalid_batch(tmp_path: Path) -> None:
    path = tmp_path / "etfs.json"
    path.write_text(
        json.dumps([sample(), sample() | {"instrument_type": "BOND"}]), encoding="utf-8"
    )
    with pytest.raises(ValidationError):
        JsonFileConnector(path).fetch()


def test_alpha_vantage_connector_maps_live_provider_responses() -> None:
    requested_functions: list[str] = []

    def fake_get(url: str, timeout: float) -> bytes:
        assert timeout == 3
        query = parse_qs(urlparse(url).query)
        assert query["apikey"] == ["test-key"]
        assert query["symbol"] == ["QQQ"]
        function = query["function"][0]
        requested_functions.append(function)
        if function == "ETF_PROFILE":
            return json.dumps(
                {
                    "net_expense_ratio": "0.20",
                    "holdings": [
                        {"symbol": "NVDA", "description": "NVIDIA Corp", "weight": "9.80"},
                        {"symbol": "MSFT", "description": "Microsoft Corp", "weight": "8.85"},
                    ],
                }
            ).encode()
        return json.dumps(
            {
                "Global Quote": {
                    "05. price": "602.1250",
                    "07. latest trading day": "2026-09-10",
                }
            }
        ).encode()

    observed_at = datetime(2026, 9, 11, 10, 30, tzinfo=UTC)
    connector = AlphaVantageConnector(
        "test-key",
        EtfListing(ticker="QQQ", exchange="XNAS", currency="USD", name="Invesco QQQ"),
        timeout=3,
        http_get=fake_get,
        clock=lambda: observed_at,
    )
    snapshot = connector.fetch()[0]
    assert requested_functions == ["ETF_PROFILE", "GLOBAL_QUOTE"]
    assert snapshot.source == "alpha-vantage"
    assert snapshot.name == "Invesco QQQ"
    assert snapshot.expense_ratio == Decimal("0.20")
    assert snapshot.quote is not None
    assert snapshot.quote.price == Decimal("602.1250")
    assert snapshot.quote.as_of == datetime(2026, 9, 10, tzinfo=UTC)
    assert snapshot.holdings_as_of == observed_at
    assert snapshot.holdings is not None
    assert snapshot.holdings[0].identifier == "alpha-vantage:NVDA"
    assert snapshot.holdings[0].weight == Decimal("9.80")


@pytest.mark.parametrize(
    ("response", "error"),
    [
        ({"Note": "request limit reached"}, ProviderLimitError),
        ({"Information": "invalid key"}, ProviderLimitError),
        ({"Error Message": "invalid symbol"}, ConnectorError),
    ],
)
def test_alpha_vantage_connector_reports_provider_errors(
    response: dict[str, str], error: type[ConnectorError]
) -> None:
    connector = AlphaVantageConnector(
        "secret-key",
        EtfListing(ticker="QQQ", exchange="XNAS", currency="USD"),
        http_get=lambda url, timeout: json.dumps(response).encode(),
    )
    with pytest.raises(error) as raised:
        connector.fetch()
    assert "secret-key" not in str(raised.value)


def test_alpha_vantage_connector_rejects_missing_quote() -> None:
    responses = iter([{"holdings": []}, {"Global Quote": {}}])
    connector = AlphaVantageConnector(
        "test-key",
        EtfListing(ticker="QQQ", exchange="XNAS", currency="USD"),
        http_get=lambda url, timeout: json.dumps(next(responses)).encode(),
    )
    with pytest.raises(ConnectorError, match="invalid ETF quote"):
        connector.fetch()
