import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)


async def protect_requests(request: Request, call_next: RequestResponseEndpoint) -> Response:
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if (
            request.headers.get("X-Requested-With") != "PortfolioRated"
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"detail": "Request not allowed."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


async def validation_error(request: Request, exc: Exception) -> JSONResponse:
    # Submitted values can contain passwords, so validation responses do not echo inputs.
    return JSONResponse({"detail": "Check the submitted fields."}, status_code=422)


async def database_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Database operation failed: %s", type(exc).__name__)
    return JSONResponse({"detail": "Service temporarily unavailable."}, status_code=503)
