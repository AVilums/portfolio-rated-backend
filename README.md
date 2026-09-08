# Market Risk Control Platform

This project is a learning and interview system for deterministic market-risk controls. It uses a layered modular FastAPI application, PostgreSQL, SQLAlchemy/Alembic, and separate API and worker workloads. The API and worker share domain and persistence code; they have different runtime responsibilities.

## Start the first slice

```bash
docker compose up --build
curl http://localhost:8000/v1/health/live
curl -X POST http://localhost:8000/v1/risk/historical-var -H "content-type: application/json" -d '{"losses":[1,3,2,4],"confidence":0.75}'
```

On PowerShell, use `curl.exe` instead of the `curl` alias, or use `Invoke-RestMethod`. Health endpoints are versioned at `/v1/health/live` and `/v1/health/ready`.

## Application layout

`src/risk_platform` is organized by application responsibility:

- `api/` contains versioned FastAPI routers and dependencies.
- `core/` contains settings, logging, and database session wiring.
- `features/` contains business capabilities such as risk.
- `models/` contains SQLAlchemy persistence models.
- `worker/` contains the background process entry point.

The risk calculation in `features/risk/calculations.py` is pure and independent of FastAPI and SQLAlchemy. The worker currently provides a healthy executable shell; job claiming is the next implementation increment.

## Kubernetes locally

Build the image into a local kind cluster and apply the local overlay:

```bash
docker build -t portfolio-risk-api:local .
kind load docker-image portfolio-risk-api:local
kubectl apply -k k8s/environments/local
kubectl -n risk-platform port-forward service/risk-api 8000:8000
```

The Kubernetes base includes a Postgres Deployment with a PVC, API and worker Deployments, Services, ConfigMap, Secret, resource requests/limits, and health probes. The Secret contains development credentials only and should be replaced by a cluster secret manager for shared environments.

The authoritative calculation is the pure function in `src/risk_platform/risk.py`. An optional LLM integration, if added later, may explain persisted results but must never produce the risk number.

## Architecture

```text
Clients / controls UI
          |
       REST API  -----> PostgreSQL (portfolios, positions, prices, risk, audit)
          ^                         ^
          |                         |
       /metrics                 Risk worker
                          (polls jobs, calculates, persists)
```

## Development roadmap

1. Add portfolio, position, and market-price CRUD with validation and idempotency keys.
2. Add a market-data ingestion boundary, stale-data checks, retry/backoff, and an outbox/audit event writer.
3. Add a database-backed risk job table and worker loop. Make job claiming safe with row locks and a lease.
4. Add integration tests against PostgreSQL, structured JSON logs, timeout/error middleware, and richer Prometheus metrics.
5. Add Docker Compose API/worker migrations and Kubernetes manifests with Secrets, ConfigMaps, probes, resource limits, and a Postgres PVC.
6. Add CI for lint, type checking, unit/API tests, migration checks, image build, and a local kind deployment.

The design keeps the API and worker as separate deployable workloads without splitting the domain into premature microservices.
