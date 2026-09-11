from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from risk_platform.api.health import router as health_router
from risk_platform.api.http import database_error, protect_requests, validation_error
from risk_platform.auth.routes import router as auth_router
from risk_platform.database import engine
from risk_platform.market_data.routes import router as market_data_router
from risk_platform.portfolio.routes import router as portfolio_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Portfolio Rated",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(portfolio_router, prefix="/api/v1")
    app.include_router(market_data_router, prefix="/api/v1")
    app.include_router(health_router, prefix="/api/v1")
    app.middleware("http")(protect_requests)
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(SQLAlchemyError, database_error)
    return app
