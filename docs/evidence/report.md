# Báo cáo Load Test: Xác định Old-Ceiling (Theo PM-152)

## 1. Mục tiêu và Kết quả (Verdict)
Báo cáo này tuân thủ contract PM-152 và dùng các artifact raw evidence dưới thư mục [nodes](./mandate-19/pm-152/nodes) và [prometheus](./mandate-19/pm-152/prometheus).

- **Verdict**: `READY_FOR_REVIEW`
- **Old Ceiling (Highest Passing Stage)**: 328 Locust users, kéo dài đủ 5 phút. Served RPS sustained ở mức 174.75 RPS.
- **Breakpoint (Failing Stage)**: 410 Locust users, SLO bị gãy ở 2 cửa sổ liên tiếp.
- **Requests-per-node Baseline**: 174.75 RPS / 9 nodes = 19.4 RPS/node.

## 2. Stage comparison
| Stage | Traffic mix | Served RPS | Browse p99 / p95 | Cart p99 / p95 | Checkout p99 / p95 | Success rate (browse/cart/checkout) | SLO status |
|---|---|---:|---:|---:|---:|---|---|
| Highest passing 328 users | Browse 70% / Cart 20% / Checkout 10% | 174.75 | 480ms / 300ms | 500ms / 320ms | 330ms / 240ms | 99.8% / 99.7% / 99.9% | Pass |
| Failing 410 users | Browse 70% / Cart 20% / Checkout 10% | 168.90 | 1180ms / 1060ms | 1240ms / 1100ms | 940ms / 820ms | 98.4% / 98.1% / 97.2% | Fail: browse/cart p95 and checkout success breach SLO |

## 3. Evidence contract & DoD summary
- [x] **Canonical node-set**: before/after snapshots recorded with distinct timestamps and a canonical node-set hash derived from `name + uid + providerID + instanceType`. Raw files: [nodes/before.json](./mandate-19/pm-152/nodes/before.json), [nodes/after.json](./mandate-19/pm-152/nodes/after.json), [nodes/timeline.jsonl](./mandate-19/pm-152/nodes/timeline.jsonl), [nodes/node-set.sha256](./mandate-19/pm-152/nodes/node-set.sha256).
- [x] **DB pool scope clarified**: the evidence in [prometheus/db_pool.json](./mandate-19/pm-152/prometheus/db_pool.json) is explicitly scoped to the product-catalog pool and therefore matches the code setting `SetMaxOpenConns(20)`.
- [x] **Raw Prometheus evidence**: [prometheus/frontend_cpu.json](./mandate-19/pm-152/prometheus/frontend_cpu.json), [prometheus/db_pool.json](./mandate-19/pm-152/prometheus/db_pool.json) and [prometheus/envoy.json](./mandate-19/pm-152/prometheus/envoy.json) include query text, exact time window and raw samples.
- [x] **Bottleneck interpretation**: the evidence shows frontend CPU saturation and throttling during the failing window, while Envoy and DB pool remained below overflow/queue pressure.

## 4. Bottleneck conclusion
Frontend CPU is the earliest saturation signal observed in the failing window. CPU per pod reaches 218m with throttling visible at the same time that p95 latency and SLO breach appear. This is the primary saturation signal to carry forward to PM-153.

## 5. Supporting artifacts
- [closure-checklist](./mandate-19/pm-152/closure-checklist.md)
- Screenshots remain as presentation artifacts only; raw evidence is stored in the JSON files above.
