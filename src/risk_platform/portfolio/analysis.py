from decimal import ROUND_HALF_UP, Decimal

from risk_platform.portfolio.schemas import Analysis, PortfolioRequest


def analyse(request: PortfolioRequest) -> Analysis:
    """HHI uses entered weights; it cannot infer underlying fund holdings or risk."""
    weights = [p.allocation / 100 for p in request.positions]
    hhi = sum((w * w for w in weights), Decimal(0))
    largest = max(request.positions, key=lambda p: p.allocation)
    effective = (1 / hhi).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return Analysis(
        concentration=float((hhi * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        effective_positions=float(effective),
        largest_allocation=float(largest.allocation),
        position_count=len(request.positions),
        observations=[
            f"{largest.ticker} is the largest position at {largest.allocation.normalize():f}%.",
            f"The allocation has the concentration of {effective:f} equally weighted positions.",
        ],
    )
