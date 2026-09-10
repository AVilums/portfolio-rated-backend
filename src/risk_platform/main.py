import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from risk_platform import auth, portfolio
from risk_platform.database import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    engine.dispose()


app = FastAPI(
    title="Portfolio Rated",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")


@app.middleware("http")
async def protect_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        # Cross-origin browsers cannot set this header without a CORS preflight.
        # This API deliberately does not enable cross-origin requests.
        if (
            request.headers.get("X-Requested-With") != "PortfolioRated"
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"detail": "Request not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Do not echo inputs (especially passwords) in validation responses.
    return JSONResponse({"detail": "Check the submitted fields."}, status_code=422)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse({"detail": "Service temporarily unavailable."}, status_code=503)


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}
