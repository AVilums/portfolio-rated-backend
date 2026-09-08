# ADR 0003: Use PostgreSQL as the system of record

## Decision

Store portfolios, positions, prices, risk calculations, audit events, and worker job state in PostgreSQL, with schema changes managed by Alembic.

## Rationale

The data is relational, needs constraints and transactions, and must support audit queries. PostgreSQL also provides row locking for safe job claiming when the worker is scaled.

## Trade-off

The first local setup has a database dependency. That cost is intentional: SQLite would hide concurrency, locking, JSON, and timestamp behavior that matter in production.
