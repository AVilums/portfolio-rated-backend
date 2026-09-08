from fastapi import APIRouter

from risk_platform.api.v1.endpoints import health, risk

router = APIRouter(prefix="/v1")
router.include_router(health.router)
router.include_router(risk.router)
