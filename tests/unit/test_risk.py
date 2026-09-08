from decimal import Decimal

import pytest

from risk_platform.features.risk.calculations import historical_var


def test_historical_var_uses_nearest_rank() -> None:
    losses = [Decimal("1"), Decimal("3"), Decimal("2"), Decimal("4")]
    assert historical_var(losses, Decimal("0.75")) == Decimal("3")


def test_historical_var_rejects_empty_observations() -> None:
    with pytest.raises(ValueError):
        historical_var([])
