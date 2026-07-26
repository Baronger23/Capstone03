# Báo cáo Load Test: Xác định Old-Ceiling (Theo PM-152)

## 1. Mục tiêu và Kết quả (Verdict)
Báo cáo này đang được dùng để đánh giá liệu PM-152 có đủ evidence để xác nhận là `DONE` hay chưa. Sau khi rà soát lại theo contract PM-152, kết luận hiện tại là `BLOCKED` cho mục đích bàn giao PM-153/155.

- **Current verdict**: `BLOCKED` (chưa đủ để xác nhận PM-152 DONE)
- **Old Ceiling (Highest Passing Stage)**: 328 Locust users, kéo dài đủ 5 phút. Served RPS sustained ở mức 174.75 RPS.
- **Breakpoint (Failing Stage)**: 410 Locust users, SLO bị gãy ở 2 cửa sổ liên tiếp.
- **Requests-per-node Baseline**: 174.75 RPS / 9 nodes = 19.4 RPS/node.

## 2. Stage comparison
| Stage | Traffic mix | Served RPS | Browse p99 / p95 | Cart p99 / p95 | Checkout p99 / p95 | Success rate (browse/cart/checkout) | SLO status |
|---|---|---:|---:|---:|---:|---|---|
| Highest passing 328 users | Browse 70% / Cart 20% / Checkout 10% | 174.75 | 480ms / 300ms | 500ms / 320ms | 330ms / 240ms | 99.8% / 99.7% / 99.9% | Pass |
| Failing 410 users | Browse 70% / Cart 20% / Checkout 10% | 168.90 | 1180ms / 1060ms | 1240ms / 1100ms | 940ms / 820ms | 98.4% / 98.1% / 97.2% | Fail: browse/cart p95 and checkout success breach SLO |

## 3. Current status against PM-152 DoD
Các phần sau đã được cải thiện và có thể xem trực tiếp ở các file dưới đây:
- [x] **Canonical node-set**: snapshot before/after có timestamp phân biệt và hash canonical đã lưu ở [nodes/before.json](./mandate-19/pm-152/nodes/before.json), [nodes/after.json](./mandate-19/pm-152/nodes/after.json), [nodes/timeline.jsonl](./mandate-19/pm-152/nodes/timeline.jsonl) và [nodes/node-set.sha256](./mandate-19/pm-152/nodes/node-set.sha256).
- [x] **DB pool scope clarified**: [prometheus/db_pool.json](./mandate-19/pm-152/prometheus/db_pool.json) đã ghi rõ đây là pool của product-catalog và phù hợp với code `SetMaxOpenConns(20)`.
- [x] **Prometheus evidence**: [prometheus/frontend_cpu.json](./mandate-19/pm-152/prometheus/frontend_cpu.json), [prometheus/db_pool.json](./mandate-19/pm-152/prometheus/db_pool.json) và [prometheus/envoy.json](./mandate-19/pm-152/prometheus/envoy.json) đã có query, exact time window và raw samples.

Tuy nhiên, các mục sau vẫn còn thiếu so với contract PM-152 và khiến trạng thái không đủ để quy về `DONE`:
- [ ] **Raw Locust runs**: chưa có thư mục raw Locust run-1/run-2, CSV hoặc run metadata để chứng minh highest passing stage và failing stage được re-run.
- [ ] **Trace evidence**: chưa có thư mục traces/ hoặc trace JSON để chứng minh bottleneck saturation và co-bottleneck.
- [ ] **Environment / load-profile / breakpoint summary**: chưa có [environment.json](./mandate-19/pm-152/environment.json), [load-profile.json](./mandate-19/pm-152/load-profile.json) hoặc [breakpoint-summary.json](./mandate-19/pm-152/breakpoint-summary.json).
- [ ] **Recovery and freeze evidence**: chưa có bằng chứng riêng về recovery sau khi hạ tải và việc không có deployment/config/flag/backup interference trong cửa sổ test.
- [ ] **Exact SLO contract provenance**: các số p99/p95 đã xuất hiện trong báo cáo, nhưng chưa có artifact riêng thể hiện exact contract và cách nó được đối chiếu với raw metric.

## 4. Bottleneck conclusion
Frontend CPU là tín hiệu bão hòa sớm nhất được ghi nhận trong cửa sổ fail, nhưng vẫn cần trace và raw Locust/Prometheus đầy đủ để đưa vào quyết định PM-152 chính thức.

## 5. Supporting artifacts
- [closure-checklist](./mandate-19/pm-152/closure-checklist.md)
- Các screenshot chỉ là presentation artifact; raw evidence còn thiếu như nêu ở trên.
