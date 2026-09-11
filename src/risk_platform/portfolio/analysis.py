from decimal import ROUND_HALF_UP, Decimal

from risk_platform.market_data.schemas import EtfSnapshot
from risk_platform.market_data.service import ResolvedEtfData
from risk_platform.portfolio.schemas import (
    AnalysedHolding,
    Analysis,
    EtfAnalysis,
    PortfolioRequest,
    UnderlyingExposure,
)


def _rounded(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def analyse(
    request: PortfolioRequest, resolved: dict[str, ResolvedEtfData] | None = None
) -> Analysis:
    """HHI uses entered weights; it cannot infer underlying fund holdings or risk."""
    weights = [p.allocation / 100 for p in request.positions]
    hhi = sum((w * w for w in weights), Decimal(0))
    largest = max(request.positions, key=lambda p: p.allocation)
    effective = (1 / hhi).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    etfs: list[EtfAnalysis] = []
    exposures: dict[str, tuple[str, Decimal]] = {}
    covered_weight = Decimal(0)
    for position in request.positions:
        item = (resolved or {}).get(position.ticker)
        if item is None or item.snapshot is None:
            etfs.append(
                EtfAnalysis(
                    ticker=position.ticker,
                    status=item.status if item else "unavailable",
                    message=item.message if item else "ETF data was not requested.",
                )
            )
            continue
        snapshot = EtfSnapshot.model_validate(item.snapshot.payload)
        covered_weight += position.allocation
        quote = snapshot.quote
        average_price = position.average_price
        price_change = (
            _rounded((quote.price / average_price - 1) * 100)
            if quote is not None and average_price is not None
            else None
        )
        holdings = snapshot.holdings or []
        analysed_holdings: list[AnalysedHolding] = []
        for holding in holdings:
            exposure = position.allocation * holding.weight / 100
            name, current = exposures.get(holding.identifier, (holding.name, Decimal(0)))
            exposures[holding.identifier] = (name, current + exposure)
            analysed_holdings.append(
                AnalysedHolding(
                    name=holding.name,
                    fund_weight=_rounded(holding.weight),
                    portfolio_exposure=_rounded(exposure),
                )
            )
        analysed_holdings.sort(key=lambda holding: holding.fund_weight, reverse=True)
        etfs.append(
            EtfAnalysis(
                ticker=position.ticker,
                status=item.status,
                message=item.message,
                snapshot_id=item.snapshot.id,
                source=snapshot.source,
                as_of=snapshot.as_of,
                currency=snapshot.currency,
                current_price=float(quote.price) if quote else None,
                price_change=price_change,
                expense_ratio=float(snapshot.expense_ratio)
                if snapshot.expense_ratio is not None
                else None,
                holdings_coverage=_rounded(sum((h.weight for h in holdings), Decimal(0)))
                if snapshot.holdings is not None
                else None,
                top_holdings=analysed_holdings[:5],
            )
        )
    underlying = [
        UnderlyingExposure(name=name, portfolio_exposure=_rounded(exposure))
        for name, exposure in sorted(exposures.values(), key=lambda value: value[1], reverse=True)[
            :10
        ]
    ]
    coverage = _rounded(covered_weight)
    observations = [
        f"{largest.ticker} is the largest position at {largest.allocation.normalize():f}%.",
        f"The allocation has the concentration of {effective:f} equally weighted positions.",
        f"Stored ETF data covers {coverage:g}% of the entered portfolio weight.",
    ]
    return Analysis(
        concentration=float((hhi * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        effective_positions=float(effective),
        largest_allocation=float(largest.allocation),
        position_count=len(request.positions),
        observations=observations,
        data_coverage=coverage,
        etfs=etfs,
        underlying_exposure=underlying,
    )
