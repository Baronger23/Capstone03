# Mandate #19 staged rollout runbook

This runbook deliberately separates observability, frontend tuning and
load-shedding enforcement. A merge to `main` must not combine all stages.

## Stage 1 — shadow observation

Configuration is promoted through
`components.frontend-proxy.envOverrides` in `values-prod.yaml`; the Envoy image
does not need a source edit for every stage:

```yaml
- name: BROWSE_RATE_LIMIT_ENABLED_PERCENT
  value: "100"
- name: BROWSE_RATE_LIMIT_ENFORCED_PERCENT
  value: "0"
```

Keep the browse token bucket at `max_tokens: 100` and
`tokens_per_fill: 50` per proxy. Run normal traffic and overload traffic for
5–15 minutes. Record:

- `browse_rate_limiter.enabled`, `ok`, `rate_limited` and `enforced`
- browse offered/served RPS
- checkout/cart status, success and p99
- frontend/frontend-proxy Ready replicas
- pod restarts, OOM and Pending pods
- node-set hash and allocatable CPU

Do not promote if route counters are absent, protected traffic is counted as
browse, or the node-set changes.

## Stage 2 — frontend request tuning

Change only the frontend CPU request to `200m`; keep the frontend HPA target at
`65%` and keep `maxReplicas` at the current baseline. Repeat the breakpoint test.

The expected scale threshold moves from about `65m` to `130m` CPU/pod. Record
p99, CPU throttling, Pending pods, checkout success and node count before
considering the next stage.

## Stage 3 — step the HPA target

Use separate reviewed changes and repeat the same test window:

```text
200m / 65%  →  200m / 70%  →  200m / 75%
```

Stop and roll back when checkout success drops below 99%, checkout p99 violates
SLO for 2–3 minutes, unexpected 5xx/timeout rises, or pod/node health changes.

Raise `maxReplicas` only in a separate capacity step after the 65% baseline has
passed. A run that adds a node is invalid for the Directive #19 density claim.

## Stage 4 — enforce gradually

Keep Stage 1 as the rollback baseline. Promote enforcement in this order:

```text
0% → 5% → 25% → 50% → 100%
```

Hold every stage for at least five minutes under the same offered load. The
next stage is allowed only if:

- protected `/api/cart` and `/api/checkout` receive zero 429;
- checkout success is at least 99% and p99 remains within SLO;
- browse 429 occurs only above the calibrated budget;
- unexpected 5xx/timeout, restart, OOM and Pending pods remain unchanged;
- node count and node-set hash remain unchanged.

Change only `BROWSE_RATE_LIMIT_ENFORCED_PERCENT` for the 5/25/50/100 promotion
steps. The 5/25/50/100 values are rollout stages, not a substitute for calibration.
Use the smallest available canary mechanism (Argo Rollouts or a separate
stable/canary proxy deployment) before sending the stage to all proxies.

## Rollback

Immediately return to the last known-good Git SHA/image and `enforced: 0` when
any stop condition occurs. Preserve the rejected run's Locust CSV, Prometheus
range output, Envoy stats and node timeline. Verify the rollback by checking
that browse 429 stops and protected checkout recovers.

## Route smoke test

After exhausting the browse bucket, verify:

```text
GET  /api/checkout       → not rate-limited
POST /api/cart           → not rate-limited
GET  /api/products/:id   → not rate-limited
GET  /                    → would be shed when enforcement is enabled
GET  /api/products       → would be shed when enforcement is enabled
```

When enforcement is enabled, shed responses must contain
`x-techx-load-shed: browse` and `x-envoy-ratelimited: true`.
