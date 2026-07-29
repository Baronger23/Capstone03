# Mandate #19 after-run evidence

Status: **RUN CAPTURED — INVALID / INCOMPLETE**

Source supplied by the engineer: `Kết quả test mandate 19.txt`. The source
contains console snapshots for 100, 150, 200, 250, 300, 350, 380 and 410 users.
It is not copied into this repository because it is outside the workspace.

This run cannot be used to claim that Directive #19 passed:

- the node set changed during the run (9 nodes at 100 users, 10 at 150 users,
  and 11 by 300 users);
- a frontend pod was Pending from the 350-user stage and had remained Pending
  for 8m49s at the 410-user snapshot;
- the captured Locust profile includes `/api/data`,
  `/api/product-ask-ai-assistant/*` and `/api/product-reviews/*`, so it is not
  the agreed 70% shedable browse / 20% cart / 10% protected checkout profile;
- no enforced overload/load-shedding evidence, 429 counters or response
  headers were supplied;
- there is no raw Locust CSV or exact-window Prometheus export.

Available observations are preserved under
`docs/evidence/mandate-19/after/`; unknown fields remain explicitly marked.

## Immutable run identity

- Git SHA: `MISSING`
- Frontend image digest: `MISSING`
- Frontend-proxy image digest: `MISSING`
- UTC test window: `MISSING`
- Load profile/version/command: `MISSING`
- SLO definition/query: `MISSING exact-window export`
- Node-set hash before: `MISSING`
- Node-set hash after: `MISSING`
- Observed node count: `9 -> 10 -> 11` (**changed; run invalid**)
- Frontend replicas at 410 users: `5` reported by HPA; one additional
  frontend pod was Pending
- Frontend-proxy replicas at 410 users: `3`

The run is invalid if the two node hashes or node counts differ.

## Before/after ceiling and density

| Measure | Before | After |
|---|---:|---:|
| Highest offered users | 328 | 410 observed |
| Peak served RPS holding SLO | 174.75 reported | Not established |
| Highest current RPS observed | N/A | 81.8 at 410 users |
| Node count | Not comparable | 9 -> 11 |
| Served RPS/node | Not comparable | Not valid: node set changed |
| Checkout success | Missing raw evidence | 7,914/7,915 in cumulative snapshot (99.987%) |
| Checkout p99 | Missing raw evidence | 490 ms cumulative at final snapshot |
| Unexpected 5xx/timeout | Missing raw evidence | One checkout failure shown; cause/status missing |

The 81.8 RPS value is a point-in-time Locust value, not a proven sustained
SLO-holding ceiling. It is lower than the reported old value of 174.75 RPS and
was measured while extra nodes had joined, so no before/after improvement or
density improvement can be calculated.

## Bottleneck removal

- Before bottleneck: frontend CPU saturation/throttling.
- Before signal and exact-window query: `MISSING`
- After observation: frontend HPA `64%/65%`, 5 replicas at 410 users
- Scheduling observation: frontend pod
  `frontend-f8b686869-dkqgl` Pending for 8m49s at the final snapshot
- Next earliest saturation point: `NOT ESTABLISHED`
- CPU throttling, queue/connection pressure and restart evidence: `MISSING`

The supplied snapshots suggest scheduling capacity became a constraint, but
they do not include `kubectl describe pod`, scheduler events, CPU throttling or
exact-window time series. Therefore the cause of Pending cannot be asserted.

## Graceful degradation

Run `mandate19_locustfile.py` with both `BrowseOverloadUser` and
`ProtectedCheckoutUser` for at least five sustained minutes above the new
ceiling.

- Browse offered/served RPS: `MISSING`
- Intentional browse 429 RPS: `MISSING`
- `x-techx-load-shed: browse` observed: `MISSING`
- `x-envoy-ratelimited: true` observed: `MISSING`
- Envoy `browse_rate_limiter.rate_limited/enforced`: `MISSING`
- Protected cart/checkout 429 count: `MISSING`
- Checkout success and p99 during shedding: `MISSING`
- OOM/restart: no new restart is visible for the hot path in the supplied
  final snapshot, but a complete stage delta is `MISSING`
- Node replacement/addition: **observed**
- Recovery after offered load drops: `MISSING`

## Raw artifacts

- Parsed stage observations:
  `docs/evidence/mandate-19/after/stage-summary.csv`
- Assessment and missing-evidence checklist:
  `docs/evidence/mandate-19/after/README.md`
- Machine-readable run status:
  `docs/evidence/mandate-19/after/run-summary.json`

Raw Locust CSV, Prometheus range-query JSON, Envoy stats/access logs and a
timestamped node/pod timeline still need to be added.

## Sign-off

- Engineer/name/date: `MISSING`
- Reviewer/name/date: `MISSING`
- Final decision: **INVALID / INCOMPLETE — rerun required**
