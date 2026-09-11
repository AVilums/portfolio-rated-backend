from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from risk_platform.auth.security import hash_password, verify_password
from risk_platform.market_data.models import EtfDataSnapshot
from risk_platform.market_data.schemas import EtfSnapshot
from risk_platform.market_data.service import ResolvedEtfData
from risk_platform.portfolio.analysis import analyse
from risk_platform.portfolio.schemas import PortfolioRequest


def portfolio(*allocations: str) -> PortfolioRequest:
    return PortfolioRequest.model_validate(
        {
            "positions": [
                {"ticker": f"ASSET{i}", "allocation": value, "average_price": "100"}
                for i, value in enumerate(allocations)
            ]
        }
    )


def test_concentration_of_one_position() -> None:
    result = analyse(portfolio("100"))
    assert result.concentration == 100
    assert result.effective_positions == 1
    assert result.largest_allocation == 100


def test_even_and_uneven_allocations() -> None:
    even = analyse(portfolio("50", "50"))
    uneven = analyse(portfolio("60", "25", "15"))
    assert even.concentration == 50
    assert even.effective_positions == 2
    assert uneven.concentration == 44.5
    assert uneven.effective_positions == 2.25
    assert uneven.position_count == 3


def test_decimal_total_and_normalization() -> None:
    request = portfolio("33.33", "33.33", "33.34")
    assert sum(p.allocation for p in request.positions) == Decimal("100")
    normalized = PortfolioRequest.model_validate(
        {"positions": [{"ticker": " avwc ", "allocation": 100, "average_price": 90.25}]}
    )
    assert normalized.positions[0].ticker == "AVWC"
    assert normalized.model_dump(mode="json")["positions"][0]["allocation"] == 100


@pytest.mark.parametrize(
    "values",
    [
        (),
        ("99",),
        ("101",),
        ("0", "100"),
        ("-1", "101"),
        ("33.333", "66.667"),
        ("NaN",),
        ("Infinity",),
        tuple("5" for _ in range(21)),
    ],
)
def test_invalid_allocations(values: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        portfolio(*values)


def test_duplicates_are_case_insensitive() -> None:
    with pytest.raises(ValidationError):
        PortfolioRequest.model_validate(
            {
                "positions": [
                    {"ticker": "AVWC", "allocation": 50, "average_price": 10},
                    {"ticker": "avwc", "allocation": 50, "average_price": 10},
                ]
            }
        )


@pytest.mark.parametrize("ticker", ["", "A B", "<script>", "A" * 21])
def test_invalid_tickers(ticker: str) -> None:
    with pytest.raises(ValidationError):
        PortfolioRequest.model_validate(
            {"positions": [{"ticker": ticker, "allocation": 100, "average_price": 10}]}
        )


@pytest.mark.parametrize("average_price", [None, 0, -1, "NaN", "Infinity"])
def test_invalid_average_price(average_price: object) -> None:
    with pytest.raises(ValidationError):
        PortfolioRequest.model_validate(
            {"positions": [{"ticker": "AVWC", "allocation": 100, "average_price": average_price}]}
        )


def test_etf_report_uses_snapshot_price_and_holdings() -> None:
    request = PortfolioRequest.model_validate(
        {"positions": [{"ticker": "ETF", "allocation": 100, "average_price": 80}]}
    )
    data = EtfSnapshot.model_validate(
        {
            "ticker": "ETF",
            "exchange": "US",
            "currency": "USD",
            "name": "ETF",
            "source": "fixture",
            "as_of": "2026-09-11T10:00:00Z",
            "expense_ratio": "0.2",
            "quote": {"price": "100", "as_of": "2026-09-10T00:00:00Z"},
            "holdings": [{"identifier": "A", "name": "Company A", "weight": 25}],
            "holdings_as_of": "2026-09-11T10:00:00Z",
        }
    )
    snapshot = EtfDataSnapshot(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        ticker="ETF",
        exchange="US",
        source="fixture",
        as_of=datetime(2026, 9, 11, 10, tzinfo=UTC),
        digest="x" * 64,
        payload=data.model_dump(mode="json"),
    )
    result = analyse(
        request,
        {"ETF": ResolvedEtfData(snapshot, "available", "Stored ETF data is current.")},
    )
    assert result.data_coverage == 100
    assert result.etfs[0].price_change == 25
    assert result.etfs[0].expense_ratio == 0.2
    assert result.etfs[0].top_holdings[0].portfolio_exposure == 25
    assert result.underlying_exposure[0].name == "Company A"


def test_passwords_are_salted_and_verified() -> None:
    encoded = hash_password("a-test-password")
    assert encoded != hash_password("a-test-password")
    assert verify_password("a-test-password", encoded)
    assert not verify_password("wrong-password", encoded)
