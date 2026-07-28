# Mandate #19 after-run evidence

Status: **NOT RUN**. Replace every `TBD` from raw runtime evidence. This file is
an evidence contract, not proof that the mandate has passed.

## Immutable run identity

- Git SHA: `TBD`
- Frontend image digest: `TBD`
- Frontend-proxy image digest: `TBD`
- UTC test window: `TBD`
- SLO definition/query: `TBD`
- Node-set hash before: `TBD`
- Node-set hash after: `TBD`
- Node count before/after: `TBD / TBD`
- Frontend Ready replicas at peak: `TBD`
- Frontend-proxy Ready replicas at peak: `TBD`

The run is invalid if the two node hashes or node counts differ.

## Before/after ceiling and density

| Measure | Before | After |
|---|---:|---:|
| Highest offered users | 328 | TBD |
| Peak served RPS holding SLO | 174.75 | TBD |
| Node count | TBD | TBD |
| Served RPS/node | `174.75 / before_nodes` | `after_rps / after_nodes` |
| Checkout success | TBD | TBD |
| Checkout p99 | TBD | TBD |
| Unexpected 5xx/timeout | TBD | TBD |

Pass requires `after RPS > 174.75`, `after RPS/node > before RPS/node`, unchanged
node-set, correct responses, and the approved SLO throughout the sustained stage.

## Bottleneck removal

- Before bottleneck: frontend CPU saturation/throttling.
- Before signal and exact-window query: `TBD`
- After signal and exact-window query: `TBD`
- Next earliest saturation point: `TBD`
- CPU throttling, queue/connection pressure and restart evidence: `TBD`

## Graceful degradation

Run `mandate19_locustfile.py` with both `BrowseOverloadUser` and
`ProtectedCheckoutUser` for at least five sustained minutes above the new
ceiling.

- Browse offered/served RPS: `TBD / TBD`
- Intentional browse 429 RPS: `TBD`
- `x-techx-load-shed: browse` observed: `TBD`
- `x-envoy-ratelimited: true` observed: `TBD`
- Envoy `browse_rate_limiter.rate_limited/enforced`: `TBD / TBD`
- Protected cart/checkout 429 count: `TBD` (must be zero)
- Checkout success and p99 during shedding: `TBD`
- OOM/restart/node replacement: `TBD` (must be zero)
- Recovery after offered load drops: `TBD`

## Raw artifacts

Store Locust CSV, Prometheus range-query JSON, Envoy stats/access logs and the
node/pod timeline under `docs/evidence/mandate-19/after/`. Screenshots may be
added for presentation but are not the source of truth.

## Sign-off

- Engineer/name/date: `TBD`
- Reviewer/name/date: `TBD`
- Final decision: `TBD`

