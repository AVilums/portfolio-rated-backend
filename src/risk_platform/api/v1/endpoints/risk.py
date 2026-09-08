import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from risk_platform.features.risk.schemas import VaRRequest, VaRResponse
from risk_platform.features.risk.services import RiskService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["risk"])


def get_risk_service() -> RiskService:
    return RiskService()


@router.post("/historical-var", response_model=VaRResponse)
async def calculate_historical_var(
    request: VaRRequest,
    service: Annotated[RiskService, Depends(get_risk_service)],
) -> VaRResponse:
    result = service.calculate_historical_var(request)
    logger.info(
        "risk_calculated",
        extra={"metric": result.metric, "observations": result.observation_count},
    )
    return result
