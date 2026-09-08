# ADR 0001: Use a modular application with separate API and worker workloads

## Decision

Keep one Python codebase with shared domain and persistence modules, 
and deploy the REST API and risk worker as separate workloads.

## Rationale

The workloads have different scaling and failure characteristics, while the domain is still small. This gives independent worker restarts and scheduling without the operational cost of multiple services and network contracts.

## Trade-off

The shared codebase requires discipline around module boundaries. We will keep HTTP adapters, worker orchestration, domain calculations, and persistence separate so either workload remains easy to test.
