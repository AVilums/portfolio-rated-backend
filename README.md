# Portfolio Rated API

A small synchronous FastAPI application with SQLAlchemy, Alembic and PostgreSQL.

## Run

Keep `portfolio-rated-frontend` beside this repository, then:

```sh
docker compose up --build -d
```

Web app: http://localhost:8080
API docs: http://localhost:8000/api/docs

Compose starts PostgreSQL, applies migrations, then starts the API and frontend.
Create the first account through the web registration form. PostgreSQL data lives
in a named volume. `docker compose down` preserves the volume.

## Structure

```text
src/risk_platform/
  api/
    health.py        Database readiness endpoint
    http.py          Request protection and safe exception responses
  auth/
    security.py      Password and token primitives
    schemas.py       Request and response contracts
    models.py        Account and login-session tables
    service.py       Registration, login and session use cases
    dependencies.py  Current-user HTTP dependency
    routes.py        Thin FastAPI adapter
  portfolio/
    schemas.py       Portfolio and report contracts
    analysis.py      Pure portfolio calculations
    models.py        Immutable report table
    service.py       Create and retrieve report use cases
    routes.py        Thin FastAPI adapter
  market_data/
    schemas.py       Provider-independent ETF snapshot contract
    connectors.py    Provider port and concrete adapters
    models.py        Snapshot table
    repository.py    Snapshot persistence and queries
    service.py       Live refresh orchestration
    routes.py        Thin FastAPI adapter
  config.py          Environment configuration
  database.py        SQLAlchemy registry, engine and request session
  application.py     FastAPI construction and module registration
  main.py            Minimal ASGI export
migrations/          Versioned schema changes
tests/               Calculation and PostgreSQL API tests
```

This is a feature-first, light clean architecture. Each feature keeps its contracts,
rules, persistence and HTTP adapter together. Routes translate HTTP and delegate to
services; services implement use cases; models and repositories own SQLAlchemy;
pure calculations and security primitives do not import FastAPI or SQLAlchemy.
Concrete provider adapters implement the small `EtfConnector` protocol.

The design deliberately avoids generic base repositories, dependency-injection
frameworks and one class per use case. Add those only when a real second
implementation needs the abstraction. The original `0001_initial` migration is
preserved for compatibility with existing databases. Its tables are unused by this
app; `0002_application` adds the three active tables without modifying existing data.

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

For allocation fractions `w`, concentration is `100 * sum(w^2)`; effective
positions is `1 / sum(w^2)`. Lower concentration means more evenly spread entered
weights. A single position yields concentration 100 and one effective position.
Results use decimal arithmetic and round to two decimal places.

These are descriptive statistics, not an assessment of investment quality or risk.
When ETF holdings are available, the report also calculates constituent exposure by
multiplying ETF weight by holding weight. It does not infer missing holdings,
geography, correlations or total return. Reports store normalized inputs, referenced
market-data IDs and a versioned analysis snapshot.

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
versioned snapshots in PostgreSQL independently of user portfolios. Portfolio
reports require ticker, current weight and average purchase price, then embed the
ETF analysis and the IDs of all market-data snapshots used.

Data flows through `EtfConnector.fetch()` -> validated `EtfSnapshot` objects ->
`repository.ingest()` -> `etf_data_snapshots`. New provider adapters implement the
connector protocol; database writes and report calculations do not belong in adapters.
`ingest()` uses a savepoint and leaves the commit to its caller. Invalid batches
do not partially import. Exact normalized-payload retries return existing IDs;
corrections create new snapshots. Latest reads use source `as_of` time, then
ingestion time, so historical backfills do not replace newer data.

Connectors are available for a local UTF-8 JSON array and Alpha Vantage's ETF
profile plus global quote APIs. The live connector requires a free API key. Request
count varies because unseen symbols may need discovery and non-US listings do not
request the US-focused profile endpoint. No scheduler is configured yet. The example
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
invalid credentials and malformed quote responses fail the whole import before
commit. Missing ETF profiles produce a valid quote-only snapshot. Alpha Vantage
currently documents 25 requests per day for free keys.

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

When a portfolio report is submitted, the API looks up each ticker in local ETF
storage. Data observed within `MARKET_DATA_MAX_AGE_HOURS` (24 by default) is reused.
Missing or older data is refreshed through Alpha Vantage when its key is configured,
then stored and referenced in the immutable report snapshot. Provider failure does
not discard the report: older data is marked stale and missing data is marked
unavailable. The client shows coverage explicitly.

Ticker-only live refreshes use Alpha Vantage symbol search and persist the resolved
provider symbol, exchange and currency with the snapshot. Subsequent refreshes reuse
that identity. When search has no match, the provider's bare-symbol US convention is
used. Import listing metadata through JSON or the operator CLI when a ticker is
ambiguous across exchanges.

MVP1 portfolio positions require `ticker`, `allocation` (current portfolio weight)
and `average_price`. The report adds latest close versus average price, expense ratio,
holdings coverage, five available constituents per ETF, and the ten largest combined
underlying exposures. Price change excludes distributions, fees and taxes.
