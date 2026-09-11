from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from risk_platform.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)


class Base(DeclarativeBase):
    """Shared SQLAlchemy registry; feature modules own their table mappings."""
    pass


def get_db() -> Iterator[Session]:
    with Session(engine) as db:
        yield db


Db = Annotated[Session, Depends(get_db)]
