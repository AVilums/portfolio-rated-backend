from risk_platform.features.risk.calculations import historical_var
from risk_platform.features.risk.schemas import VaRRequest, VaRResponse


class RiskService:
    """Application orchestration for risk use cases.

    Persistence is intentionally not required by the first pure-calculation slice.
    The repository dependency will be injected here when risk jobs are added.
    """

    def calculate_historical_var(self, request: VaRRequest) -> VaRResponse:
        return VaRResponse(
            value=historical_var(request.losses, request.confidence),
            confidence=request.confidence,
            observation_count=len(request.losses),
        )
