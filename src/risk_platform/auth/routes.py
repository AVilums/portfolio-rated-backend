from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response

from risk_platform.auth.dependencies import COOKIE_NAME, CurrentUser
from risk_platform.auth.models import User
from risk_platform.auth.schemas import Credentials, Registration, UserResponse
from risk_platform.auth.service import (
    AccountExistsError,
    AccountLockedError,
    InvalidCredentialsError,
    authenticate,
    create_session,
    register_user,
    revoke_session,
)
from risk_platform.config import get_settings
from risk_platform.database import Db

router = APIRouter(prefix="/auth", tags=["auth"])


def _start_session(user: User, request: Request, response: Response, db: Db) -> None:
    settings = get_settings()
    max_age = settings.session_hours * 3600
    token = create_session(
        db,
        user,
        request.cookies.get(COOKIE_NAME),
        lifetime=timedelta(seconds=max_age),
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="strict",
        path="/api",
    )


@router.post("/register", response_model=UserResponse, status_code=201)
def register(registration: Registration, request: Request, response: Response, db: Db) -> User:
    try:
        user = register_user(db, registration.email, registration.password)
    except AccountExistsError as error:
        raise HTTPException(409, "An account already exists for this email.") from error
    _start_session(user, request, response, db)
    return user


@router.post("/login", response_model=UserResponse)
def login(credentials: Credentials, request: Request, response: Response, db: Db) -> User:
    try:
        user = authenticate(db, credentials.email, credentials.password, now=datetime.now(UTC))
    except AccountLockedError as error:
        raise HTTPException(429, "Too many attempts. Try again in five minutes.") from error
    except InvalidCredentialsError as error:
        raise HTTPException(401, "Email or password is incorrect.") from error
    _start_session(user, request, response, db)
    return user


@router.get("/session", response_model=UserResponse)
def session(user: CurrentUser) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db) -> None:
    revoke_session(db, request.cookies.get(COOKIE_NAME, ""))
    response.delete_cookie(
        COOKIE_NAME,
        path="/api",
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="strict",
    )
