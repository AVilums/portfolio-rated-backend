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
  portfolio/     Separate schemas, allocation calculations and report routes
  market_data/   ETF connector contract, JSON import, storage and read routes
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

## ETF data foundation (MVP1)

The first market-data module supports ETFs only. It stores source-attributed,
versioned snapshots in PostgreSQL independently of user portfolios. The existing
allocation report API remains compatible; ETF report calculations and the average
purchase price input are the next layer, not part of this ingestion step.

Data flows through `EtfConnector.fetch()` -> validated `EtfSnapshot` objects ->
`ingest()` -> `etf_data_snapshots`. New provider adapters implement the connector
protocol; database writes and report calculations do not belong in adapters.
`ingest()` uses a savepoint and leaves the commit to its caller. Invalid batches
do not partially import. Exact normalized-payload retries return existing IDs;
corrections create new snapshots. Latest reads use source `as_of` time, then
ingestion time, so historical backfills do not replace newer data.

Connectors are available for a local UTF-8 JSON array and Alpha Vantage's ETF
profile plus global quote APIs. The live connector requires a free API key and
makes two provider requests per ETF. No scheduler is configured yet. The example
file is synthetic, not real ETF data.

From the backend directory, with `DATABASE_URL` set for your PostgreSQL database:

```sh
python -m alembic upgrade head
python -m risk_platform.market_data examples/etf-snapshots.json
```

For a live US-listed ETF, put the key in `.env` and supply listing facts because
Alpha Vantage's ETF profile response does not include them:

```env
ALPHA_VANTAGE_API_KEY=your-free-key
```

```sh
python -m risk_platform.market_data --alpha-vantage-symbol QQQ \
  --exchange XNAS --currency USD --name "Invesco QQQ Trust"
```

The connector uses only the standard library HTTP client, enforces a 10-second
timeout, and never includes the API key in raised errors. Provider throttling,
invalid credentials and malformed responses fail the whole import before commit.
Alpha Vantage currently documents 25 requests per day for free keys, so one run
uses two of those requests.

For the local Compose database accessed from the host, use port **5433**. The
command prints snapshot IDs after commit. Import is an operator CLI action;
signed-in users cannot upload or overwrite the shared dataset.

Authenticated read endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/market-data/etfs/latest?ticker=DEMO&exchange=XNAS&source=example` | Latest data for a listing and source |
| GET | `/api/v1/market-data/etfs/snapshots/{id}` | A specific historical snapshot |

These endpoints read local storage only and return 404 for missing data. Market
data is shared across accounts; user reports remain private. Future reports
should reference the snapshot IDs they used for reproducibility.

The schema is defined in `market_data/schemas.py`; an example is provided in
`examples/etf-snapshots.json`:

- Identify a listing by uppercase ticker and exchange (prefer an exchange MIC),
  with uppercase ISO currency. Source is a lowercase provider identifier.
  Optional ISIN identifies the security, not the listing.
- `as_of` is the time the live response was observed (or the supplied snapshot
  timestamp for JSON imports). Quotes and holdings have their own timezone-aware
  timestamps, no later than the snapshot timestamp. Alpha Vantage supplies the
  quote's trading date but no holdings publication date, so its `holdings_as_of`
  records observation time. Ingestion time is recorded separately.
- Quote prices are unadjusted prices in the listing currency. Use decimal strings
  for prices and percentages; API decimals are also serialized as strings.
- Expense ratio and holding weights use percentage units: `0.15` means 0.15%,
  and `30` means 30%. Partial holdings are allowed. `holdings_coverage` reports
  their summed weight; missing holdings return null, not an inferred zero.
- The initial holdings format accepts nonnegative constituents totaling at most
  100%. Leveraged, short or derivative exposure breakdowns need an extended schema;
  import profile/quote data only for those funds rather than coercing exposures.

Migration `0003_etf_data` adds only the snapshot table. Existing reports and legacy
market tables are preserved. No live data is seeded automatically.
