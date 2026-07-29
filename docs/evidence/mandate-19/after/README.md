# Mandate #19 after-run assessment

## Outcome

The supplied run is preserved as an **invalid/incomplete after attempt**. It
must not be presented as proof that Mandate #19 passed.

What the source does establish:

- load was increased from 100 to 410 concurrent users;
- point-in-time RPS increased from 20.5 to 81.8;
- frontend HPA increased from 2 to 5 replicas;
- frontend-proxy HPA increased from 2 to 3 replicas;
- the final cumulative Locust snapshot shows 7,915 checkout requests, one
  failure and checkout p99 of 490 ms;
- a frontend pod remained Pending for at least 8m49s.

What invalidates the same-infrastructure comparison:

- node count changed from 9 to 10 and then 11;
- node identities also changed between snapshots;
- therefore neither a valid after ceiling nor RPS/node improvement can be
  calculated from this run.

## Evidence still required

Provide the following for a valid rerun:

1. Run identity:
   - Git SHA;
   - frontend and frontend-proxy image digests;
   - exact UTC start/end per stage;
   - Locust version, command and load-profile SHA.
2. Fixed infrastructure:
   - `kubectl get nodes -o json` before and after;
   - node identity hash sampled during the run;
   - Karpenter NodeClaim create/delete events;
   - mark the run invalid immediately if any node joins, leaves or is replaced.
3. Canonical traffic and raw load output:
   - 70% shedable browse (`/` and `/api/products`);
   - 20% cart;
   - 10% protected checkout journey;
   - headless Locust CSV for every stage;
   - load-generator CPU/network to prove the generator is not the bottleneck.
4. Exact-window SLO exports:
   - browse success and p95;
   - cart success;
   - checkout success and approved p99 threshold;
   - unexpected 5xx/timeouts;
   - one-minute samples for every sustained five-minute stage.
5. Saturation evidence:
   - HPA current/desired/Ready replicas and conditions over time;
   - per-pod CPU, memory and CPU-throttling ratio;
   - Pending reason from `kubectl describe pod` and scheduler events;
   - Envoy active/pending/overflow counters;
   - downstream connection-pool/queue-depth metrics.
6. Graceful-degradation run above the new ceiling:
   - enforcement percentage and effective per-proxy token-bucket capacity;
   - browse 429 count/RPS;
   - `x-techx-load-shed: browse`;
   - `x-envoy-ratelimited: true`;
   - Envoy `rate_limited` and `enforced` counter deltas;
   - zero 429 on `/api/cart`, `/api/checkout` and `/api/products/<id>`;
   - checkout success/p99 while browse is shed;
   - no OOM/restart/node change and successful recovery after load drops.

## Required rerun decision

Use the highest five-minute stage that passes every approved SLO in every
one-minute window as the new ceiling. Reproduce that passing stage and the
first failing stage once. Only then calculate:

```text
after_density = after_ceiling_served_rps / fixed_node_count
improvement_percent = ((after_density / before_density) - 1) * 100
```

Intentional browse 429 responses must be reported separately and must not be
counted as successfully served business throughput.
