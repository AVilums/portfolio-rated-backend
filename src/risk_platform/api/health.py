from fastapi import APIRouter
from sqlalchemy import text

from risk_platform.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}
