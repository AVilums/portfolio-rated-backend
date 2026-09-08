from decimal import Decimal


def historical_var(losses: list[Decimal], confidence: Decimal = Decimal("0.99")) -> Decimal:
    """Return the historical loss quantile using a deterministic nearest-rank rule."""
    if not losses or not Decimal("0") < confidence < Decimal("1"):
        raise ValueError("losses must be non-empty and confidence must be between 0 and 1")
    ordered = sorted(losses)
    rank_decimal: Decimal = (len(ordered) * confidence).to_integral_value(
        rounding="ROUND_CEILING"
    )
    rank = max(1, int(rank_decimal))
    return ordered[rank - 1]


def gross_exposure(quantity: Decimal, price: Decimal) -> Decimal:
    return abs(quantity * price)
