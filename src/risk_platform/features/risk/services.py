from risk_platform.features.risk.calculations import historical_var
from risk_platform.features.risk.schemas import VaRRequest, VaRResponse


class RiskService:
    """Application orchestration for risk use cases.

    Persistence is intentionally not required by the first pure-calculation slice.
    A repository dependency can be injected when stored calculations are added.
    """

    def calculate_historical_var(self, request: VaRRequest) -> VaRResponse:
        return VaRResponse(
            value=historical_var(request.losses, request.confidence),
            confidence=request.confidence,
            observation_count=len(request.losses),
        )
