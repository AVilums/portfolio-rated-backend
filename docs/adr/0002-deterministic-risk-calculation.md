# ADR 0002: Keep authoritative risk calculations deterministic

## Decision

Risk metrics are implemented as typed, tested Python domain functions. Inputs, algorithm version, observations, and outputs are persisted with each calculation.

## Rationale

Risk control needs reproducibility, explainability, and auditability. Historical VaR must produce the same result for the same inputs regardless of model availability or prompt wording.

## Trade-off

The system does not use an LLM to discover or calculate a metric. A later LLM adapter may explain a persisted result, but its output has no authority over the number or control decision.
