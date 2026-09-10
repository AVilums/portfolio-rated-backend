# Portfolio Rated API

A small synchronous FastAPI application with SQLAlchemy, Alembic and PostgreSQL.

## Run

Keep `portfolio-rated-frontend` beside this repository, then:

```sh
docker compose up --build -d
```

Web app: http://localhost:8080
API docs: http://localhost:8000/api/docs
Local login: `demo@example.com` / `local-portfolio-password`

Compose starts PostgreSQL, applies migrations, creates the initial account if
missing, then starts the API and frontend. PostgreSQL data lives in a named volume.
The database has no host port. `docker compose down` preserves the volume.

Local credentials appear only in the development Compose configuration.
Override `INITIAL_EMAIL` and `INITIAL_PASSWORD` before first startup if desired.
Seeding is idempotent and never replaces an existing password.

## Structure

```text
src/risk_platform/
  config.py       Environment configuration
  database.py     Engine and per-request database session
  models.py       Users, login sessions, report snapshots
  auth.py         Password verification, sessions, login throttling
  portfolio.py    Input contract, allocation calculations, report routes
  main.py         Application, request protection and safe errors
  seed.py         Explicit initial-account creation
migrations/       Versioned schema changes
tests/            Calculation and PostgreSQL API tests
```

There are no repository/service wrappers, async database plumbing, Kubernetes
manifests, or metrics stack. The original `0001_initial` migration is preserved
for compatibility with existing databases. Its tables are unused by this app;
`0002_application` adds the three active tables without modifying existing data.

## API

All routes begin with `/api/v1`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /auth/register | Create an account and set session cookie |
| POST | /auth/login | Verify credentials and set session cookie |
| GET | /auth/session | Current account |
| POST | /auth/logout | Revoke session |
| POST | /portfolio/analyse | Validate, calculate and save a report |
| GET | /portfolio/latest | Latest report for the current account, or null |
| GET | /portfolio/reports/{id} | Owned report; other accounts receive 404 |
| GET | /health | Database readiness |

Mutation requests require `X-Requested-With: PortfolioRated`. Cross-site browser
requests are rejected; CORS is intentionally not enabled. The frontend uses a
same-origin proxy. Validation errors do not echo submitted data, and database
errors return a generic message.

Passwords use PBKDF2-HMAC-SHA256 with random salts and 600,000 iterations.
Opaque session tokens are stored as SHA-256 hashes; cookies are HTTP-only,
SameSite=Strict and expire after 12 hours. Production mode also requires Secure
cookies. Five failed attempts lock a known account for five minutes.

## Calculations

For allocation fractions `w`, concentration is `100 Ã— sum(wÂ²)`; effective
positions is `1 / sum(wÂ²)`. Lower concentration means more evenly spread entered
weights. A single position yields concentration 100 and one effective position.
Results use decimal arithmetic and round to two decimal places.

These are allocation statistics, not an assessment of investment quality or risk.
Inputs cannot reveal ETF overlap, geography, correlations or underlying holdings.
Reports store normalized inputs and a versioned analysis snapshot.

## Checks

```sh
docker compose --profile test run --build --rm test
docker compose --profile test stop test-db
```

The test profile migrates a separate ephemeral PostgreSQL database. Each test uses
an outer transaction and rolls back endpoint commits after completion.

For local Python tooling, create a virtual environment and install `.[dev]`:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy src
python -m pytest -m "not integration"
```

For a separate local API process, configure `DATABASE_URL` for your own PostgreSQL
database, set `APP_ENV=local`, apply `alembic upgrade head`, and run
`uvicorn risk_platform.main:app --reload`. Compose already runs the API on port 8000.
