from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from risk_platform.auth.models import User
from risk_platform.auth.service import resolve_session
from risk_platform.database import Db

COOKIE_NAME = "portfolio_session"


def current_user(request: Request, db: Db) -> User:
    user = resolve_session(db, request.cookies.get(COOKIE_NAME, ""), now=datetime.now(UTC))
    if user is None:
        raise HTTPException(401, "Sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
