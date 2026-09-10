from decimal import Decimal

import pytest
from pydantic import ValidationError

from risk_platform.auth import hash_password, verify_password
from risk_platform.portfolio import PortfolioRequest, analyse


def portfolio(*allocations: str) -> PortfolioRequest:
    return PortfolioRequest.model_validate(
        {
            "positions": [
                {"ticker": f"ASSET{i}", "allocation": value} for i, value in enumerate(allocations)
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
        {"positions": [{"ticker": " avwc ", "allocation": 100}]}
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
                    {"ticker": "AVWC", "allocation": 50},
                    {"ticker": "avwc", "allocation": 50},
                ]
            }
        )


@pytest.mark.parametrize("ticker", ["", "A B", "<script>", "A" * 21])
def test_invalid_tickers(ticker: str) -> None:
    with pytest.raises(ValidationError):
        PortfolioRequest.model_validate({"positions": [{"ticker": ticker, "allocation": 100}]})


def test_passwords_are_salted_and_verified() -> None:
    encoded = hash_password("a-test-password")
    assert encoded != hash_password("a-test-password")
    assert verify_password("a-test-password", encoded)
    assert not verify_password("wrong-password", encoded)
