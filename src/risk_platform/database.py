from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from risk_platform.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    with Session(engine) as db:
        yield db
