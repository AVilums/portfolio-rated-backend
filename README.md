# Market Risk Control Platform

A small FastAPI and PostgreSQL service for deterministic market-risk calculations. The application is packaged as a modular monolith with a REST API, SQLAlchemy persistence models, Alembic migrations, Docker Compose support, and Kubernetes manifests for local clusters.

## Current capabilities

- FastAPI API with versioned routes
- Liveness and database readiness endpoints
- Deterministic historical VaR calculation
- SQLAlchemy models for portfolios, positions, market prices, risk calculations, and audit events
- Alembic migration setup
- Prometheus-compatible `/metrics` endpoint
- Docker Compose and Kubernetes deployment templates

The current VaR endpoint calculates and returns a result synchronously. Persistence-backed portfolio workflows and stored risk calculations can be added incrementally.

## Run locally with Docker Compose

Start the API and PostgreSQL:

```powershell
docker compose up --build -d
docker compose ps
```

Check the service:

```powershell
Invoke-RestMethod http://localhost:8000/v1/health/live
Invoke-RestMethod http://localhost:8000/v1/health/ready
```

Calculate historical VaR in PowerShell:

```powershell
$body = @{
    losses = @(1, 3, 2, 4)
    confidence = 0.75
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://localhost:8000/v1/risk/historical-var" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

Useful endpoints:

```text
http://localhost:8000/docs
http://localhost:8000/metrics
```

Stop the local services with:

```powershell
docker compose down
```

## Run locally on Kubernetes with kind

Create or verify a kind cluster:

```powershell
kind create cluster --name kind --wait 5m
kubectl config use-context kind-kind
kubectl cluster-info
kubectl get nodes
```

Build and load the application image:

```powershell
docker build -t portfolio-risk-api:local .
kind load docker-image portfolio-risk-api:local --name kind
```

Apply the local Kubernetes overlay:

```powershell
kubectl apply -k k8s/environments/local
kubectl -n risk-platform get pods
```

Forward the API service to the host:

```powershell
kubectl -n risk-platform port-forward service/risk-api 8000:8000
```

The Kubernetes base includes an API Deployment, PostgreSQL Deployment, Services, ConfigMap, Secret, PVC, resource limits, and health probes. The Secret contains development credentials and should be replaced with a managed secret in shared environments.

## Project layout

```text
src/risk_platform/
├── api/             FastAPI routers and dependencies
├── core/            Configuration, logging, and database wiring
├── features/        Business capabilities and risk calculations
├── models/          SQLAlchemy persistence models
└── main.py          Application entry point

migrations/          Alembic environment and revisions
tests/unit/           Pure calculation tests
tests/integration/    API tests
k8s/                  Kubernetes base and local overlay
```

The risk calculation in `src/risk_platform/features/risk/calculations.py` is pure and independent of FastAPI and SQLAlchemy. This keeps the authoritative calculation easy to test and reproduce.

## Development checks

```powershell
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src
.\.venv\Scripts\python.exe -m pytest
docker compose config --quiet
kubectl kustomize k8s/environments/local
```

## Roadmap

1. Add portfolio, position, and market-price CRUD with validation and idempotency keys.
2. Add market-data freshness checks, retries, timeouts, and audit event persistence.
3. Persist risk calculations with input snapshots and algorithm versions.
4. Add PostgreSQL integration tests and structured JSON logging.
5. Add CI for linting, type checking, tests, migrations, image builds, and Kubernetes manifest validation.
