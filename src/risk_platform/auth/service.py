import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from risk_platform.auth.models import LoginSession, User
from risk_platform.auth.security import hash_password, token_hash, verify_password

DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class AccountExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class AccountLockedError(Exception):
    pass


def register_user(db: Session, email: str, password: str) -> User:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise AccountExistsError
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise AccountExistsError from error
    return user


def authenticate(db: Session, email: str, password: str, *, now: datetime) -> User:
    user = db.scalar(select(User).where(User.email == email).with_for_update())
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if user is None:
        raise InvalidCredentialsError
    if user.locked_until and user.locked_until > now:
        raise AccountLockedError
    if not valid:
        if user.locked_until:
            user.failed_attempts = 0
            user.locked_until = None
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.locked_until = now + timedelta(minutes=5)
        db.commit()
        raise InvalidCredentialsError
    user.failed_attempts = 0
    user.locked_until = None
    return user


def create_session(
    db: Session, user: User, previous_token: str | None, *, lifetime: timedelta
) -> str:
    now = datetime.now(UTC)
    db.execute(delete(LoginSession).where(LoginSession.expires_at <= now))
    if previous_token:
        db.execute(
            delete(LoginSession).where(LoginSession.token_hash == token_hash(previous_token))
        )
    token = secrets.token_urlsafe(32)
    db.add(
        LoginSession(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=now + lifetime,
        )
    )
    db.commit()
    return token


def resolve_session(db: Session, token: str, *, now: datetime) -> User | None:
    session = db.get(LoginSession, token_hash(token))
    if session is None or session.expires_at <= now:
        return None
    return db.get(User, session.user_id)


def revoke_session(db: Session, token: str) -> None:
    db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
    db.commit()
