import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from risk_platform.config import get_settings
from risk_platform.database import get_db
from risk_platform.models import LoginSession, User

COOKIE_NAME = "portfolio_session"
PASSWORD_ITERATIONS = 600_000
Db = Annotated[Session, Depends(get_db)]
router = APIRouter(prefix="/auth", tags=["auth"])


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PASSWORD_ITERATIONS)
    return "$".join((str(PASSWORD_ITERATIONS), salt, digest.hex()))


def verify_password(password: str, encoded: str) -> bool:
    iterations, salt, expected = encoded.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class Registration(Credentials):
    password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str


def current_user(request: Request, db: Db) -> User:
    token = request.cookies.get(COOKIE_NAME, "")
    session = db.get(LoginSession, token_hash(token))
    if session is None or session.expires_at <= datetime.now(UTC):
        raise HTTPException(401, "Sign in to continue.")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def start_session(user: User, request: Request, response: Response, db: Session) -> None:
    now = datetime.now(UTC)
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(previous)))
    token = secrets.token_urlsafe(32)
    max_age = get_settings().session_hours * 3600
    db.add(
        LoginSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=now + timedelta(seconds=max_age),
        )
    )
    db.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="strict",
        path="/api",
    )


@router.post("/register", response_model=UserResponse, status_code=201)
def register(registration: Registration, request: Request, response: Response, db: Db) -> User:
    if db.scalar(select(User.id).where(User.email == registration.email)) is not None:
        raise HTTPException(409, "An account already exists for this email.")
    user = User(email=registration.email, password_hash=hash_password(registration.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "An account already exists for this email.") from error
    start_session(user, request, response, db)
    return user


@router.post("/login", response_model=UserResponse)
def login(credentials: Credentials, request: Request, response: Response, db: Db) -> User:
    # Serialize known-account attempts so concurrent requests cannot bypass the lock.
    user = db.scalar(select(User).where(User.email == credentials.email).with_for_update())
    now = datetime.now(UTC)
    valid = verify_password(credentials.password, user.password_hash if user else DUMMY_HASH)
    if user is None:
        raise HTTPException(401, "Email or password is incorrect.")
    if user.locked_until and user.locked_until > now:
        raise HTTPException(429, "Too many attempts. Try again in five minutes.")
    if not valid:
        if user.locked_until:
            user.failed_attempts = 0
            user.locked_until = None
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.locked_until = now + timedelta(minutes=5)
        db.commit()
        raise HTTPException(401, "Email or password is incorrect.")
    user.failed_attempts = 0
    user.locked_until = None
    start_session(user, request, response, db)
    return user


@router.get("/session", response_model=UserResponse)
def session(user: CurrentUser) -> User:
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db) -> None:
    token = request.cookies.get(COOKIE_NAME, "")
    db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
    db.commit()
    response.delete_cookie(
        COOKIE_NAME,
        path="/api",
        httponly=True,
        secure=get_settings().secure_cookies,
        samesite="strict",
    )
