from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from risk_platform.api.v1.endpoints import health, risk
from risk_platform.core.config import get_settings
from risk_platform.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(title=settings.app_name, version="0.1.0")
app.include_router(health.router, prefix="/v1")
app.include_router(risk.router, prefix="/v1")
Instrumentator().instrument(app).expose(app)
