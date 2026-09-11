import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from risk_platform.auth import COOKIE_NAME, hash_password, token_hash
from risk_platform.config import get_settings
from risk_platform.database import get_db
from risk_platform.main import app
from risk_platform.market_data.connectors import JsonFileConnector
from risk_platform.market_data.models import EtfDataSnapshot
from risk_platform.market_data.service import ingest, latest
from risk_platform.models import LoginSession, Report, User

pytestmark = pytest.mark.integration
HEADERS = {"X-Requested-With": "PortfolioRated"}
PASSWORD = "test-account-password"
PAYLOAD = {
    "positions": [
        {"ticker": " avwc ", "allocation": 60},
        {"ticker": "AVWS", "allocation": 25},
        {"ticker": "AVEM", "allocation": 15},
    ]
}


@pytest.fixture
def db() -> Iterator[Session]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL or run the Compose test profile.")
    engine = create_engine(url)
    # Each test uses a rollback-only outer transaction, including endpoint commits.
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("APP_ENV", "test")
    get_settings.cache_clear()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, base_url="http://testserver", headers=HEADERS) as client:
        yield client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def account(db: Session) -> User:
    user = User(email=f"{uuid4()}@example.com", password_hash=hash_password(PASSWORD))
    db.add(user)
    db.commit()
    return user


def login(client: TestClient, account: User) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": account.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    assert "password_hash" not in response.text


def test_login_save_restore_logout(client: TestClient, account: User, db: Session) -> None:
    assert client.get("/api/v1/auth/session").status_code == 401
    login(client, account)
    token = client.cookies.get(COOKIE_NAME)
    assert token
    assert db.get(LoginSession, token_hash(token)) is not None
    assert client.get("/api/v1/portfolio/latest").json() is None
    response = client.post("/api/v1/portfolio/analyse", json=PAYLOAD)
    assert response.status_code == 201
    report = response.json()
    assert report["analysis"]["concentration"] == 44.5
    assert report["positions"][0]["ticker"] == "AVWC"
    assert db.scalar(select(Report).where(Report.user_id == account.id)) is not None
    assert client.get("/api/v1/portfolio/latest").json() == report
    assert client.get(f"/api/v1/portfolio/reports/{report['id']}").json() == report
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401
    client.cookies.set(COOKIE_NAME, token, path="/api")
    assert client.get("/api/v1/portfolio/latest").status_code == 401
    client.cookies.clear()
    login(client, account)
    assert client.get("/api/v1/portfolio/latest").json() == report


def test_register_starts_session_and_rejects_duplicate(client: TestClient, db: Session) -> None:
    email = f"{uuid4()}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"  {email.upper()}  ", "password": PASSWORD},
    )
    assert response.status_code == 201
    assert response.json()["email"] == email
    assert client.get("/api/v1/auth/session").status_code == 200
    assert db.scalar(select(User).where(User.email == email)) is not None
    client.post("/api/v1/auth/logout")
    duplicate = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD})
    assert duplicate.status_code == 409


def test_register_requires_a_strong_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"{uuid4()}@example.com", "password": "too-short"},
    )
    assert response.status_code == 422


def test_other_account_cannot_read_report(client: TestClient, account: User, db: Session) -> None:
    login(client, account)
    report = client.post("/api/v1/portfolio/analyse", json=PAYLOAD).json()
    client.post("/api/v1/auth/logout")
    other = User(email=f"{uuid4()}@example.com", password_hash=hash_password(PASSWORD))
    db.add(other)
    db.commit()
    login(client, other)
    assert client.get("/api/v1/portfolio/latest").json() is None
    assert client.get(f"/api/v1/portfolio/reports/{report['id']}").status_code == 404


def test_invalid_requests_are_not_saved(client: TestClient, account: User, db: Session) -> None:
    login(client, account)
    for positions in [
        [],
        [{"ticker": "AVWC", "allocation": 99}],
        [{"ticker": "AVWC", "allocation": 50}, {"ticker": "avwc", "allocation": 50}],
        [{"ticker": "AVWC", "allocation": 99.999}],
    ]:
        assert (
            client.post("/api/v1/portfolio/analyse", json={"positions": positions}).status_code
            == 422
        )
    assert db.scalar(select(Report).where(Report.user_id == account.id)) is None


def test_expired_session_is_rejected(client: TestClient, account: User, db: Session) -> None:
    login(client, account)
    session = db.get(LoginSession, token_hash(client.cookies[COOKIE_NAME]))
    assert session
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert client.get("/api/v1/portfolio/latest").status_code == 401


def test_repeated_failed_login_locks_account(client: TestClient, account: User) -> None:
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={
                    "email": account.email,
                    "password": "wrong",
                },
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": account.email,
                "password": PASSWORD,
            },
        ).status_code
        == 429
    )


def test_csrf_header_is_required(client: TestClient, account: User) -> None:
    client.headers.pop("X-Requested-With")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": account.email,
                "password": PASSWORD,
            },
        ).status_code
        == 403
    )


def test_cross_site_requests_are_rejected(client: TestClient) -> None:
    assert (
        client.post("/api/v1/auth/logout", headers={"Sec-Fetch-Site": "cross-site"}).status_code
        == 403
    )


def test_validation_does_not_echo_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid",
            "password": "secret-test-password",
        },
    )
    assert response.status_code == 422
    assert "secret-test-password" not in response.text


def test_etf_ingestion_and_authenticated_reads(
    client: TestClient, account: User, db: Session, tmp_path: Path
) -> None:
    from test_market_data import sample

    path = tmp_path / "etfs.json"
    path.write_text(json.dumps([sample()]), encoding="utf-8")
    connector = JsonFileConnector(path)
    first = ingest(db, connector)
    db.commit()
    assert ingest(db, connector) == first
    db.commit()
    query = "ticker=test&exchange=xnas&source=fixture"
    assert client.get(f"/api/v1/market-data/etfs/latest?{query}").status_code == 401
    login(client, account)
    result = client.get(f"/api/v1/market-data/etfs/latest?{query}")
    assert result.status_code == 200
    assert result.json()["holdings_coverage"] == "65.2"
    assert result.json()["id"] == str(first[0])
    assert client.get(f"/api/v1/market-data/etfs/snapshots/{first[0]}").json() == result.json()

    # A correction remains separately addressable, even within one transaction.
    path.write_text(json.dumps([sample() | {"name": "Corrected ETF name"}]), encoding="utf-8")
    correction = ingest(db, connector)
    assert correction != first
    assert latest(db, "TEST", "XNAS", "fixture").id == correction[0]
    assert db.get(EtfDataSnapshot, first[0]).payload["name"] == "Synthetic ETF"

    # Backfilled historical data must not replace the most recent snapshot.
    older = sample() | {
        "as_of": "2026-09-01T20:00:00Z",
        "quote": None,
        "holdings": None,
        "holdings_as_of": None,
    }
    path.write_text(json.dumps([older]), encoding="utf-8")
    ingest(db, connector)
    assert latest(db, "TEST", "XNAS", "fixture").id == correction[0]
    assert latest(db, "TEST", "XLON", "fixture") is None
    assert latest(db, "TEST", "XNAS", "another-source") is None
    assert (
        client.get(
            "/api/v1/market-data/etfs/latest?" + query.replace("test", "missing")
        ).status_code
        == 404
    )
    assert client.get(f"/api/v1/market-data/etfs/snapshots/{uuid4()}").status_code == 404


def test_etf_invalid_batch_does_not_persist(db: Session, tmp_path: Path) -> None:
    from pydantic import ValidationError
    from test_market_data import sample

    path = tmp_path / "invalid.json"
    path.write_text(json.dumps([sample(), sample() | {"currency": "invalid"}]), encoding="utf-8")
    with pytest.raises(ValidationError):
        ingest(db, JsonFileConnector(path))
    assert latest(db, "TEST", "XNAS", "fixture") is None
