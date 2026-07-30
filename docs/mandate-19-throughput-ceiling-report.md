# Mandate #19 — Báo cáo triển khai: Biết trần của mình và nâng trần bằng hiệu suất

**Ngày thực hiện:** 23–29/07/2026  
**Người thực hiện:** CDO01  
**Trụ:** Performance Efficiency · chạm Cost Optimization · Reliability  
**Trạng thái:** Báo cáo evidence đã hợp nhất — implementation đã triển khai; run after 7 node đã được ghi nhận, các acceptance gap được nêu rõ tại mục 8
**ADR:** [`docs/adr/0011-mandate-19-throughput-ceiling-load-shedding.md`](adr/0011-mandate-19-throughput-ceiling-load-shedding.md)  
**Runbook rollout:** [`docs/runbooks/mandate-19-staged-rollout.md`](runbooks/mandate-19-staged-rollout.md)  
**Kế hoạch triển khai:** [`docs/mandate-19-implement-plan.md`](mandate-19-implement-plan.md)  
**Evidence before:** [`docs/evidence/mandate-19/pm-152/`](evidence/mandate-19/pm-152/)  
**Evidence after template:** [`docs/evidence/mandate-19/after-run-template.md`](evidence/mandate-19/after-run-template.md)
**Video demo:** [Mandate #19 — throughput/load-shedding demo](https://drive.google.com/file/d/1JyAhSKoYIt3bmh_mudLjEhNN_GOOWi2o/view?usp=sharing)
**Locust after HTML:** [`docs/evidence/mandate-19/after/locust-after-2026-07-29.html`](evidence/mandate-19/after/locust-after-2026-07-29.html)

---

## 1. Mục tiêu & ràng buộc

Directive #19 yêu cầu trả lời 4 câu hỏi cùng lúc:

1. Trần thông lượng thật của hệ hiện tại là bao nhiêu trước khi SLO gãy.
2. Có nâng được trần đó trên cùng hạ tầng hiện có hay không.
3. Service nào bão hòa sớm nhất và đã nới nó bằng cách gì.
4. Khi tải vượt trần thì hệ có xuống mềm để bảo vệ checkout hay không.

**Ràng buộc bắt buộc:**

- Không thêm node trong bài test before/after.
- Không nâng trần bằng mua thêm hạ tầng.
- Giữ correctness và reliability của luồng browse → cart → checkout.
- Storefront vẫn public, cổng vận hành vẫn private, không đụng flagd.

---

## 2. Cách giải bài Mandate #19

Mandate này được chia thành 3 phần kỹ thuật độc lập để giảm rủi ro merge và giúp đo được before/after đúng nghĩa:

| Hạng mục | Mục tiêu | Trạng thái |
|---|---|---|
| PM-152 — Breakpoint discovery | Đo trần before thật, tìm bottleneck sớm nhất | ✅ Đã có before |
| PM-153 — Throughput tuning | Nâng trần bằng tuning trên cùng node set | ✅ Tuning đã triển khai; after 7-node run đã ghi nhận |
| PM-154 — Load shedding | Shed browse, bảo vệ cart/checkout khi overload | ✅ Enforced route policy đã triển khai; 429/header runtime capture còn thiếu |

### 2.1. Breakpoint discovery

Chạy Locust theo profile cố định, tăng tải theo từng stage đến khi một trong hai điều kiện xuất hiện:

- p99 vượt SLO đã chốt cho run
- error rate tăng vượt ngưỡng chấp nhận

Kết quả dùng để xác định:

- highest passing throughput
- breakpoint throughput
- bottleneck đầu tiên
- requests-per-node baseline

### 2.2. Throughput tuning

Không scale node, chỉ tăng throughput trên cùng hạ tầng bằng các thay đổi sau:

- tăng HPA target của các hot path an toàn để mỗi pod gánh nhiều request hơn trước khi scale
- tăng giới hạn `circuit_breakers.max_requests` ở Envoy để bỏ bottleneck proxy sớm
- tăng CPU request của frontend để giảm throttling và phản ánh usage sát hơn
- giữ checkout/cart bảo thủ hơn để không đánh đổi luồng doanh thu

### 2.3. Graceful degradation

Khi tải vượt trần, không để hệ sập hàng loạt. Thay vào đó:

- phân loại route thành `protected` và `shedable`
- bảo vệ `/api/checkout`, `/api/cart`, `/api/products/<id>`
- chỉ shed browse/catch-all bằng `envoy.filters.http.local_ratelimit`
- rollout theo shadow trước, enforce tăng dần sau khi xác nhận route match đúng

---

## 3. Before — hiện trạng trước tối ưu

Nguồn số liệu before hiện tại lấy từ:

- [`docs/evidence/mandate-19/pm-152/breakpoint-summary.json`](evidence/mandate-19/pm-152/breakpoint-summary.json)
- raw Locust / Prometheus / node timeline trong thư mục `docs/evidence/mandate-19/pm-152/`

### 3.1. Kết quả breakpoint before

| Chỉ số | Before |
|---|---:|
| Highest passing stage quan sát được | 400 users |
| Failing stage | 410 users |
| Current RPS tại ảnh giữ SLO | 76.2 |
| Current RPS tại ảnh breakpoint | 73.9 |
| Current failures tại breakpoint | 1% |
| Bottleneck sớm nhất | frontend CPU saturation and throttling |
| Co-bottleneck loại trừ được | frontend-proxy chưa overflow; DB pool product-catalog chưa cạn |
| Failure window | Chưa xác định được từ screenshot |

### 3.2. Kết luận before

Before run cho thấy hệ chưa gãy vì frontend-proxy hay DB pool. Nút thắt xuất hiện sớm nhất là `frontend` bị bão hòa CPU và bắt đầu throttling. Đây là bottleneck quyết định trần cũ, nên tuning phải tập trung nâng density ở lớp frontend trước.

### 3.3. Density before

| Chỉ số | Before |
|---|---|
| Node count trong run before | 9 |
| Current RPS snapshot | 76.2 |
| Requests-per-node snapshot | 8.47 RPS/node |

Node-set before được chụp ở đầu và cuối run, cùng có `nodeCount: 9` và cùng hash
`5d2b7b7885fa55fcc97318ff15fc81fe235edd4cbe98894422ee42811ef7ec5d`.

**Công thức:**

```text
before_density = before_served_rps / fixed_node_count
```

---

## 4. Thay đổi đã triển khai để nâng trần

### 4.1. Tuning throughput trên cùng hạ tầng

Các thay đổi code/config cho phần nâng trần gồm:

| Thành phần | Thay đổi | Mục đích |
|---|---|---|
| `frontend` | tăng CPU request | giảm throttling, phản ánh usage thực hơn |
| HPA hot path | điều chỉnh target utilization theo stage | để mỗi pod chịu được nhiều request hơn trước khi scale |
| `frontend-proxy` Envoy | tăng `circuit_breakers.max_requests` | bỏ bottleneck proxy khi tải tăng |
| Benchmark discipline | giữ nguyên node set khi so sánh before/after | bảo vệ claim density |

### 4.2. Thay đổi graceful degradation

`frontend-proxy` được đổi từ một catch-all route sang phân loại route có chủ đích:

| Route class | Route | Hành vi |
|---|---|---|
| `checkout_protected` | `/api/checkout` | không bị shed |
| `cart_protected` | `/api/cart` | không bị shed |
| `product_detail_protected` | `/api/products/<id>` | không bị shed |
| `browse_shedable` | `/` và browse/listing | bị local rate limit khi quá tải |

Load shedding dùng `local_ratelimit` của Envoy:

- `filter_enabled: 100`
- `filter_enforced: 100` cho browse sau khi đã hoàn tất shadow/route gates
- global fallback vẫn `LOCAL_RATE_LIMIT_ENFORCED_PERCENT=0` để protected routes
  không bị shed bởi bucket dùng chung

### 4.3. Nguyên tắc rollout an toàn

- Không merge cùng lúc HPA tuning và enforce 100%.
- Shadow mode trước, xác nhận classification đúng rồi mới bật enforce.
- Enforce theo tỷ lệ tăng dần: `0% -> 5% -> 25% -> 50% -> 100%`.
- Canary hoặc rollout theo stage nếu cần giảm blast radius.

---

## 5. After — chỗ cập nhật sau khi chạy test

Phần này để trống có cấu trúc để cập nhật ngay sau khi bạn chạy after benchmark hợp lệ.

### 5.1. Kết quả breakpoint after

| Chỉ số | Before | After | Delta |
|---|---:|---:|---:|
| Highest passing stage | 400 users (screenshot-observed) | 300 users (provisional) | -100 users |
| Failing stage | 410 users | 350 users (provisional) | -60 users |
| Served RPS giữ SLO | Chưa có exact-window; current snapshot 76.2 | 63.25 RPS average tại 300 users | Không so sánh sustained với snapshot |
| Breakpoint served RPS | Chưa có exact-window; current snapshot 73.9 | 71.20 RPS average tại 350 users | Không so sánh sustained với snapshot |
| Primary bottleneck | frontend CPU saturation and throttling | Recommendation CPU 71% / HPA target 65% tại failing candidate 350 users; frontend đã scale 2→3 replica và hạ còn 63%/65% | Frontend bottleneck đã được nới; điểm nóng đầu tiên tại vùng SLO gãy dịch sang recommendation |
| Co-bottlenecks | proxy không overflow, DB pool chưa cạn | Frontend-proxy 62%/65% tại 350 users, sau đó 71%/65% tại 400 users; product-catalog 51%/65% tại 350 và 57%/65% tại 400; không có bằng chứng Envoy overflow hoặc DB pool cạn | Proxy trở thành saturation candidate kế tiếp tại 400 users; DB pool vẫn được loại trừ |

### 5.2. Density before/after

| Chỉ số | Before | After | Delta |
|---|---:|---:|---:|
| Node count trong từng run | 9 | 7 xuyên suốt run after | 0 trong nội bộ mỗi run |
| Served RPS giữ SLO | Chưa có exact-window; current snapshot 76.2 | 63.25 RPS tại stage 300 (provisional) | Chưa thể so sánh hợp lệ |
| Requests-per-node | 8.47 (snapshot) | 9.04 (provisional) | Chưa thể kết luận từ snapshot |

**Diễn giải node đúng:** run after không scale node theo tải. Bộ ảnh after mới
bao phủ các stage 10, 300, 350 và 400 users; panel `Node count (Karpenter burst)`
ở checkpoint 350 users, cửa sổ `Last 1 hour`, ghi `Mean: 7, Max: 7`. Người
chạy xác nhận các stage sau tiếp tục giữ 7 node, nhưng không có ảnh node riêng
cho từng stage 410–900. Dữ liệu `9 → 10 → 11` trong
`docs/evidence/mandate-19/after/run-summary.json` và hai ảnh node cũ thuộc một
run khác đã bị loại, không phải run after 7-node dùng trong mục 5.4–5.5.

Tuy nhiên, baseline before lịch sử dùng 9 node còn after dùng 7 node. Vì vậy
không được trình bày hai node-set này là cùng một node-set vật lý. Bảng density
đã chuẩn hóa theo RPS/node, nhưng claim bắt buộc “before/after cùng node-set”
vẫn cần một baseline 7-node trước tuning hoặc node-set hash 7-node trước/sau
run canonical để mentor kiểm chứng.

**Công thức:**

```text
after_density = after_served_rps / fixed_node_count
improvement_percent = ((after_density / before_density) - 1) * 100
```

### 5.3. Graceful degradation after

| Kiểm tra | Kỳ vọng | After |
|---|---|---|
| Browse overload | có 429 có chủ đích | FAIL — Locust HTML ghi 0 HTTP 429 |
| Header `x-techx-load-shed: browse` | xuất hiện | Chưa có capture |
| Header `x-envoy-ratelimited: true` | xuất hiện | Chưa có capture |
| Checkout 429 | bằng 0 | PASS — toàn artifact không có HTTP 429; vẫn có 500/503 |
| Cart 429 | bằng 0 | PASS — toàn artifact không có HTTP 429; vẫn có 503 |
| Checkout success | >= 99% | PASS về tỷ lệ tổng; degraded ở tải cao |
| Checkout p99 trong overload | giữ trong SLO | FAIL — vượt 300 ms từ vùng 350 users |
| Node count | không đổi | PASS cho cửa sổ ảnh 10–400 — node panel Mean 7 / Max 7; stage sau dựa trên operator record |
| OOM / restart / pending bất thường | không có | Không quan sát thấy trong evidence stage 7-node |

### 5.4. Nhật ký stage after

Phần Locust/SLO dưới đây đã được đối chiếu lại với 12 ảnh trong
`tests/kyverno/mandate-19/test_slo_after/`. Các con số HPA, pod CPU và node CPU
không xuất hiện trong 12 ảnh này là operator output được ghi lại khi chạy test,
không phải dữ liệu đọc từ ảnh. Bảng image-grounded độc lập nằm ở mục 5.6.

#### Stage 10 users — PASS sơ bộ

**Trạng thái:** PASS sơ bộ; cần CSV/HTML exact-window để chốt served RPS và
failure rate toàn stage.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 10 |
| Node count trong cửa sổ test | 7 |
| Frontend replicas | 2 |
| Frontend HPA CPU | 6% / target 65% |
| Frontend-proxy replicas | 2 |
| Frontend-proxy HPA CPU | 11% / target 65% |
| Frontend pod CPU | 16m, 11m |
| Frontend-proxy pod CPU | 5m, 6m |
| Browse success | 100% trong biểu đồ rolling 1h; gauge rolling 24h 99.7274% |
| Browse latency | p95 mean 37 ms; p99 mean 48.1 ms |
| Cart success | 100% |
| Cart latency | p95 mean 12.4 ms; p99 mean khoảng 50.7 ms |
| Checkout success | 100% |
| Checkout latency | p95 mean 69.6 ms; p99 mean khoảng 97.3 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |
| Saturation | không; CPU node cao nhất 10%, HPA hot path chưa cần scale |

Locust endpoint snapshot đã ghi nhận:

| Endpoint | Requests | Fails | p99 |
|---|---:|---:|---:|
| `GET /` | 1,824 | 0 | 40 ms |
| `GET /api/cart` | 5,467 | 1 | 45 ms |
| `POST /api/cart` | 10,890 | 0 | 72 ms |
| `POST /api/checkout` | 3,648 | 0 | 170 ms |

Kết luận stage: tải 10 users còn rất xa saturation; checkout/cart giữ SLO,
frontend và frontend-proxy còn headroom lớn. Chưa dùng stage này để tính
throughput ceiling vì ảnh Locust chỉ hiển thị current RPS tại thời điểm chụp
và số liệu tích lũy, không phải served RPS trung bình của exact test window.

**Lưu ý tính hợp lệ hạ tầng:** một snapshot node-set cũ có 10 node, nhưng run
after canonical mà người chạy vừa xác nhận có 7 node và giữ nguyên 7 node qua
toàn bộ stage. Snapshot 10-node cũ và biểu đồ 9→10→11 node đã được loại khỏi
claim canonical; không dùng chúng để đối chiếu với run 7-node.

#### Stage 300 users — cần xác minh exact-window

**Trạng thái:** chưa chốt PASS/FAIL. Availability vẫn đạt nhưng đã xuất hiện
dấu hiệu saturation ở frontend và latency spike cần đối chiếu đúng cửa sổ
5 phút của stage.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 300 |
| Current RPS tại thời điểm chụp | 64 |
| Current failures | 0% |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 9.14 |
| Frontend replicas | 2 |
| Frontend HPA CPU | 76% / target 65% |
| Frontend-proxy replicas | 2 |
| Frontend-proxy HPA CPU | 56% / target 65% |
| Product-catalog HPA CPU | 43% / target 65% |
| Recommendation HPA CPU | 52% / target 65% |
| Frontend pod CPU | 155m, 142m |
| Frontend-proxy pod CPU | 29m, 27m |
| Node CPU cao nhất | 47% |
| Browse success rolling 1h | 100% |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse latency rolling 1h | p95 mean 40.6 ms, max 164 ms; p99 mean 58.3 ms, max 376 ms |
| Cart latency rolling 1h | p95 mean 15.0 ms, max 98.3 ms; p99 mean 56.9 ms, max 488 ms |
| Checkout latency rolling 1h | p95 mean 76.9 ms, max 275 ms; p99 mean 110 ms, max 553 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 2,326 | 0 | 610 ms | 1,300 ms | 3.4 |
| `GET /api/cart` | 6,029 | 1 | 19 ms | 180 ms | 4.4 |
| `POST /api/cart` | 12,105 | 0 | 27 ms | 120 ms | 9.8 |
| `POST /api/checkout` | 4,073 | 0 | 100 ms | 230 ms | 3.7 |

Đánh giá:

- Availability gate đang đạt: current failure 0%, dashboard cho browse/cart/
  checkout success 100%.
- `frontend` là thành phần bão hòa sớm nhất tại snapshot này: CPU HPA 76%
  vượt target 65%, trong khi proxy 56% và các downstream chính thấp hơn.
- Chưa có bằng chứng hệ sập, node thiếu capacity hoặc proxy cạn tài nguyên.
- Locust `GET /` p99 tích lũy 1,300 ms không được dùng một mình để kết luận
  stage fail vì thống kê có thể bao gồm stage trước; cần CSV exact-window.
- Checkout p99 max 553 ms trên biểu đồ rolling 1h vượt đường 300 ms trong một
  spike. Cần xác định spike có nằm trong stage 300 users và có kéo dài đủ cửa
  sổ SLO hay không.
- `64 / 7 = 9.14 RPS/node` chỉ là density snapshot, chưa phải sustained density
  dùng cho kết luận Mandate #19.

#### Stage 350 users — failing candidate về checkout p99

**Trạng thái:** FAIL sơ bộ theo latency gate; cần CSV exact-window để chốt
breakpoint canonical. Availability vẫn đạt và hệ không sập.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 350 |
| Current RPS tại thời điểm chụp | 70.5 |
| Current failures | 0% |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 10.07 |
| Frontend replicas | 3 |
| Frontend HPA CPU | 63% / target 65% |
| Frontend-proxy replicas | 2 |
| Frontend-proxy HPA CPU | 62% / target 65% |
| Product-catalog HPA CPU | 51% / target 65% |
| Recommendation replicas / HPA CPU | 1 / 71% trên target 65% |
| Frontend pod CPU | 103m, 154m, 121m |
| Frontend-proxy pod CPU | 30m, 32m |
| Node CPU cao nhất | 45% |
| Browse success rolling 1h | 100% |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse latency rolling 1h | p95 mean 42.4 ms, max 164 ms; p99 mean 66.5 ms, max 376 ms |
| Cart latency rolling 1h | p95 mean 17.2 ms, max 98.3 ms; p99 mean 62.7 ms, max 488 ms |
| Checkout latency rolling 1h | p95 mean 84.7 ms, max 275 ms; p99 mean 124 ms, max 553 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 2,695 | 0 | 590 ms | 1,300 ms | 2.3 |
| `GET /api/cart` | 7,001 | 1 | 38 ms | 250 ms | 5.5 |
| `POST /api/cart` | 14,064 | 0 | 34 ms | 200 ms | 11.4 |
| `POST /api/checkout` | 4,778 | 0 | 130 ms | 350 ms | 3.7 |

Đánh giá:

- HPA frontend phản ứng đúng sau saturation ở stage 300: replica tăng từ 2
  lên 3 và utilization hạ từ 76% xuống 63%, không cần thêm node.
- Checkout vẫn đạt 100% success nhưng Locust p99 350 ms vượt đường SLO 300 ms;
  Grafana cũng ghi nhận checkout p99 max 553 ms. Nếu exact-window xác nhận
  p99 >300 ms theo evaluation window đã thống nhất thì 350 users là failing
  stage.
- Recommendation bắt đầu bão hòa ở 71%/65% và có thể là bottleneck kế tiếp
  sau khi frontend đã được HPA nới.
- Frontend-proxy gần target ở 62%/65% nhưng chưa có bằng chứng connection,
  queue hoặc memory exhaustion.
- Không có dấu hiệu toàn hệ thống sập: failure hiện tại 0%, node CPU còn
  headroom, không thấy Pending/OOM/restart.
- Chưa quan sát browse 429 trong evidence stage này. Với browse request rate
  tối đa khoảng 79.4 req/s và hai proxy có aggregate sustained budget xấp xỉ
  100 RPS, việc chưa shed ở stage này là phù hợp với cấu hình.
- `70.5 / 7 = 10.07 RPS/node` chỉ là density snapshot. Sustained RPS/node phải
  tính lại từ CSV exact-window.

#### Stage 400 users — FAIL về checkout p99, hệ vẫn giữ availability

**Trạng thái:** FAIL theo latency gate. Đây là failing stage chắc chắn hơn
stage 350; cần CSV exact-window để chốt sustained served RPS tại breakpoint.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 400 |
| Current RPS tại thời điểm chụp | 78.6 |
| Current failures | 0% |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 11.23 |
| Frontend replicas | 3 |
| Frontend HPA CPU | 63% / target 65% |
| Frontend-proxy HPA replicas | 3 |
| Frontend-proxy HPA CPU | 71% / target 65% |
| Product-catalog HPA CPU | 57% / target 65% |
| Recommendation replicas / HPA CPU | 2 / 38% trên target 65% |
| Frontend pod CPU | 121m, 131m, 127m |
| Frontend-proxy pod CPU đang có metrics | 34m, 37m |
| Node CPU cao nhất | 41% |
| Browse success rolling 1h | 100% |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse latency rolling 1h | p95 mean 43.4 ms, max 164 ms; p99 mean 71.4 ms, max 376 ms |
| Cart latency rolling 1h | p95 mean 19.1 ms, max 98.3 ms; p99 mean khoảng 68.3 ms, max 488 ms |
| Checkout latency rolling 1h | p95 mean 95.7 ms, max 308 ms; p99 mean 148 ms, max 603 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 3,142 | 0 | 600 ms | 1,200 ms | 1.9 |
| `GET /api/cart` | 8,108 | 1 | 62 ms | 420 ms | 4.9 |
| `POST /api/cart` | 16,332 | 0 | 49 ms | 250 ms | 12.9 |
| `POST /api/checkout` | 5,511 | 0 | 180 ms | 490 ms | 4.1 |

Đánh giá:

- Checkout success vẫn 100% nhưng Locust p99 490 ms và Grafana p99 max
  603 ms đều vượt SLO 300 ms. Stage 400 vì vậy FAIL về latency.
- Hệ không sập toàn bộ: current failure 0%, cart/checkout availability giữ
  100%, không thấy OOM/restart và node count vẫn 7.
- Frontend sau tuning vẫn ổn định ở 3 replica và 63%/65%. Recommendation đã
  scale từ 1 lên 2 replica và utilization hạ xuống 38%.
- Frontend-proxy trở thành saturation candidate tiếp theo ở 71%/65% và HPA
  báo 3 replica. `kubectl top pod` mới có metrics cho hai pod, nên cần kiểm tra
  pod thứ ba đang ContainerCreating, Pending hay chưa có Metrics Server sample.
- Node CPU chỉ tối đa 41%, chứng minh breakpoint không đến từ cạn CPU toàn
  cluster.
- Chưa quan sát browse 429. Browse request rate tối đa khoảng 89.6 req/s vẫn
  dưới aggregate sustained browse budget xấp xỉ 100 RPS của hai proxy đã Ready;
  vì vậy graceful-degradation demo cần một browse-only overload riêng vượt
  budget.
- `78.6 / 7 = 11.23 RPS/node` chỉ là density snapshot; không dùng thay cho
  sustained RPS/node của exact-window.

#### Stage 410 users — FAIL SLO nhưng không còn sập như before

**Trạng thái:** FAIL theo checkout latency; PASS về containment/availability
tại snapshot. Đây là cùng offered-user threshold từng là failing stage của
before, nhưng after không ghi nhận collapse.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 410 |
| Current RPS tại thời điểm chụp | 86.8 |
| Current failures | 0% |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 12.40 |
| Frontend replicas | 3 |
| Frontend HPA CPU | 61% / target 65% |
| Frontend-proxy replicas | 3 |
| Frontend-proxy HPA CPU | 53% / target 65% |
| Product-catalog replicas / HPA CPU | 2 / 71% trên target 65% |
| Recommendation replicas / HPA CPU | 2 / 46% trên target 65% |
| Frontend pod CPU | 139m, 141m, 132m |
| Frontend-proxy pod CPU | 6m, 36m, 38m |
| Node CPU cao nhất | 59% |
| Browse success rolling 1h | 100% |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse latency rolling 1h | p95 mean 45.7 ms, max 164 ms; p99 mean 78.0 ms, max 376 ms |
| Checkout latency rolling 1h | p95 mean 107 ms, max 308 ms; p99 mean 165 ms, max 603 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 3,565 | 0 | 580 ms | 1,200 ms | 2.7 |
| `GET /api/cart` | 9,279 | 1 | 89 ms | 530 ms | 5.6 |
| `POST /api/cart` | 18,649 | 0 | 63 ms | 310 ms | 14.7 |
| `POST /api/checkout` | 6,272 | 0 | 220 ms | 580 ms | 5.1 |

Đánh giá:

- So với before, 410 users không còn làm hệ collapse tại snapshot: current
  failure 0%, checkout/cart success 100%, không có OOM/restart và node count
  giữ nguyên 7.
- Stage vẫn FAIL yêu cầu “RPS đỉnh giữ SLO”: checkout p99 580 ms vượt SLO
  300 ms; cart GET p99 530 ms và cart POST p99 310 ms cũng cho thấy tail
  latency đã suy giảm.
- HPA đã phân phối tải tốt hơn: frontend và frontend-proxy đều có 3 replica,
  recommendation có 2 replica, không thêm node.
- Product-catalog là saturation candidate tiếp theo ở 71%/65%, trong khi
  frontend và proxy đã hạ dưới target sau scale.
- Browse rate trên Grafana đạt tối đa khoảng 99.5 req/s. Với 3 frontend-proxy
  Ready và bucket 50 RPS/proxy, aggregate budget tại stage này xấp xỉ 150 RPS;
  vì vậy chưa có 429 là phù hợp. Cần browse-only overload vượt hẳn 150 RPS để
  demo shedding và xác nhận protected-route 429 bằng 0.
- `86.8 / 7 = 12.40 RPS/node` chỉ là snapshot. Before cũng chỉ có snapshot
  76.2 RPS tại stage 400, nên tuyệt đối chưa dùng hai số này để tuyên bố trần
  after cao hơn. Cần CSV exact-window và xác nhận transaction mix/profile giống
  before trước khi so sánh throughput.

#### Stage 500 users — FAIL SLO, overload vẫn được chứa

**Trạng thái:** FAIL rõ ràng theo checkout latency; hệ vẫn giữ availability
và node count không đổi.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 500 |
| Current RPS tại thời điểm chụp | 103.3 |
| Current failures | 0% |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 14.76 |
| Frontend HPA replicas | 4 |
| Frontend HPA CPU | 78% / target 65% |
| Frontend-proxy replicas | 3 |
| Frontend-proxy HPA CPU | 62% / target 65% |
| Product-catalog HPA replicas | 3 |
| Product-catalog HPA CPU | 82% / target 65% |
| Recommendation replicas / HPA CPU | 2 / 53% trên target 65% |
| Frontend pod CPU đang có metrics | 141m, 159m, 172m |
| Frontend-proxy pod CPU | 10m, 43m, 41m |
| Node CPU cao nhất | 70% |
| Browse success rolling 1h | 100% (dashboard rounding) |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse request rate | max khoảng 103 req/s |
| Browse error request rate | mean khoảng 0.0102 req/s |
| Browse latency rolling 1h | p95 mean 49.4 ms, max 164 ms; p99 mean 87.8 ms, max 376 ms |
| Cart latency rolling 1h | p95 mean 24.3 ms, max 98.3 ms; p99 mean 88.1 ms, max 591 ms |
| Checkout latency rolling 1h | p95 mean 127 ms, max 370 ms; p99 mean 203 ms, max 681 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 4,239 | 0 | 570 ms | 1,200 ms | 2.4 |
| `GET /api/cart` | 10,933 | 1 | 140 ms | 690 ms | 6.9 |
| `POST /api/cart` | 22,169 | 1 | 95 ms | 480 ms | 17.9 |
| `POST /api/checkout` | 7,433 | 0 | 320 ms | 700 ms | 5.6 |

Đánh giá:

- Stage FAIL chắc chắn: checkout p99 700 ms vượt xa target 300 ms; checkout
  p95 cũng đã tăng lên 320 ms trong Locust snapshot.
- Hệ vẫn không collapse: current failure 0%, success dashboard 100%, không thấy
  OOM/restart và node count vẫn là 7.
- Frontend và product-catalog đều vượt target, lần lượt 78%/65% và 82%/65%;
  HPA báo tăng lên 4 và 3 replica. `kubectl top pod` chưa có metrics cho toàn bộ
  replica mới, nên cần kiểm tra Ready/Pending sau stabilization.
- Node CPU cao nhất tăng lên 70% nhưng cluster chưa cạn CPU tổng thể.
- Browse rate max khoảng 103 RPS vẫn dưới aggregate budget xấp xỉ 150 RPS của
  3 frontend-proxy. Dashboard có error request rate rất nhỏ, nhưng Locust
  snapshot chưa ghi browse failure và chưa có response headers. Không được kết
  luận đó là load shedding cho tới khi bắt được HTTP 429 cùng
  `x-techx-load-shed: browse` và `x-envoy-ratelimited: true`.
- `103.3 / 7 = 14.76 RPS/node` là density snapshot, không phải sustained
  density dùng để so trước/sau.

#### Stage 600 users — FAIL SLO nặng, hệ chưa collapse

**Trạng thái:** FAIL rõ ràng theo latency; availability vẫn được giữ tại
snapshot và node count không đổi.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 600 |
| Current RPS tại thời điểm chụp | 121.4 |
| Current failures | 0% |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 17.34 |
| Frontend replicas | 5 |
| Frontend HPA CPU | 72% / target 65% |
| Frontend-proxy replicas | 3 |
| Frontend-proxy HPA CPU | 65% / target 65% |
| Product-catalog replicas / HPA CPU | 3 / 64% trên target 65% |
| Recommendation replicas / HPA CPU | 2 / 65% trên target 65% |
| Frontend pod CPU | 159m, 140m, 125m, 155m, 177m |
| Frontend-proxy pod CPU | 12m, 42m, 44m |
| Node CPU cao nhất | 70% |
| Browse success rolling 1h | 100% (dashboard rounding) |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse request rate | max khoảng 123 req/s |
| Browse error request rate | mean khoảng 0.00712 req/s |
| Browse latency rolling 1h | p95 mean 54.4 ms, max 164 ms; p99 mean 99.5 ms, max 376 ms |
| Cart latency rolling 1h | p95 mean 28.2 ms, max 98.3 ms; p99 mean 106 ms, max 591 ms |
| Checkout latency rolling 1h | p95 mean 141 ms, max 604 ms; p99 mean 223 ms, max 786 ms |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 4,893 | 0 | 640 ms | 1,600 ms | 2.6 |
| `GET /api/cart` | 12,522 | 1 | 240 ms | 860 ms | 9.4 |
| `POST /api/cart` | 25,438 | 1 | 150 ms | 600 ms | 20.3 |
| `POST /api/checkout` | 8,511 | 0 | 490 ms | 970 ms | 6.8 |

Đánh giá:

- Stage FAIL nặng về tail latency: checkout p99 970 ms, hơn ba lần target
  300 ms; checkout p95 cũng tăng lên 490 ms.
- Hệ vẫn giữ availability tại snapshot: current failure 0%, success dashboard
  100%, không thấy OOM/restart và node count giữ nguyên 7.
- HPA đã scale frontend lên 5 replica hoàn toàn trên cùng node set. Frontend,
  proxy, product-catalog và recommendation đều quanh hoặc trên target, cho thấy
  hot path đang tiến gần saturation đồng thời.
- Node CPU cao nhất 70%; chưa có bằng chứng cạn CPU toàn cluster nhưng placement
  không đều khiến một số node nóng hơn rõ rệt.
- Browse max khoảng 123 RPS vẫn thấp hơn aggregate browse budget xấp xỉ 150 RPS
  của 3 proxy, nên chưa thấy 429 là phù hợp. Graceful-degradation demo cần
  browse-only sustained load >150 RPS hoặc test trực tiếp từng proxy bucket.
- `121.4 / 7 = 17.34 RPS/node` là snapshot, chưa phải sustained density dùng
  để chốt mandate.

#### Stage 700 users — FAIL SLO, load-shedding candidate xuất hiện

**Trạng thái:** FAIL nặng về latency và browse success. Hệ vẫn không collapse;
evidence có dấu hiệu browse được shed trong khi cart/checkout availability được
giữ, nhưng còn thiếu HTTP status/header để xác nhận 429 có chủ đích.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 700 |
| Current RPS tại thời điểm chụp | 147.1 |
| Current failures | 0% tại thời điểm chụp |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 21.01 |
| Frontend replicas | 5 |
| Frontend HPA CPU | 68% / target 65% |
| Frontend-proxy replicas | 3 |
| Frontend-proxy HPA CPU | 71% / target 65% |
| Product-catalog replicas / HPA CPU | 4 / 72% trên target 65% |
| Recommendation replicas / HPA CPU | 2 / 75% trên target 65% |
| Frontend pod CPU | 118m, 111m, 113m, 120m, 126m |
| Frontend-proxy pod CPU | 17m, 45m, 35m |
| Node CPU cao nhất | 74% |
| Browse success rolling 1h | mean 100%, min 99.2% |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | 100% |
| Browse request rate | max khoảng 144 req/s |
| Browse error request rate | mean 0.226 req/s, max 1.09 req/s |
| Browse latency rolling 1h | p95 mean 65.5 ms, max 339 ms; p99 mean 122 ms, max 651 ms |
| Cart latency rolling 1h | p95 mean 32.1 ms, max 98.3 ms; p99 mean khoảng 122 ms, max 591 ms |
| Checkout latency rolling 1h | p95 mean 175 ms, max 792 ms; p99 mean 264 ms, max khoảng 1.02 s |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 5,542 | 0 | 890 ms | 1,600 ms | 3.1 |
| `GET /api/cart` | 14,227 | 1 | 390 ms | 1,000 ms | 13.2 |
| `POST /api/cart` | 28,596 | 3 | 220 ms | 820 ms | 25.4 |
| `POST /api/checkout` | 9,579 | 2 | 750 ms | 1,200 ms | 9.0 |

Đánh giá:

- Stage FAIL rõ ràng: checkout p99 1,200 ms và p95 750 ms; browse success min
  99.2% cũng thấp hơn SLO 99.5%.
- Hệ không collapse: node count giữ 7, dashboard cart/checkout success vẫn
  100%, không thấy OOM/restart. Tuy nhiên Locust đã có một số failure tích lũy
  ở cart/checkout, nên phải kiểm tra status code để bảo đảm protected-route 429
  bằng 0 và không có 5xx/timeout mới.
- Browse đạt max khoảng 144 RPS, sát aggregate token budget khoảng 150 RPS của
  3 proxy. Do phân phối traffic/burst không hoàn toàn đều, một bucket per-proxy
  có thể cạn trước aggregate cap. Browse error rate tăng và success min giảm
  trong khi cart/checkout dashboard vẫn 100% là dấu hiệu load-shedding candidate.
- Chưa đủ bằng chứng để tuyên bố graceful degradation PASS: cần bắt lỗi browse
  là HTTP 429 có `x-techx-load-shed: browse` và
  `x-envoy-ratelimited: true`, đồng thời chứng minh mọi lỗi protected route
  không phải 429.
- Tất cả hot-path HPA chính đều quanh hoặc vượt target: frontend 68%, proxy
  71%, product-catalog 72%, recommendation 75%. Đây là vùng saturation đa
  service, không còn là một bottleneck đơn lẻ.
- Node CPU cao nhất 74%; cluster vẫn còn capacity tổng thể nhưng placement tiếp
  tục không đều.
- `147.1 / 7 = 21.01 RPS/node` là density snapshot, chưa phải sustained
  density canonical.

#### Stage 800 users — graceful degradation rõ, checkout còn sống nhưng latency fail

**Trạng thái:** PASS về ưu tiên availability/containment; FAIL về latency SLO.
Browse suy giảm có chủ đích/có kiểm soát trong khi cart và checkout vẫn giữ
success rate cao, node count không đổi và hệ không collapse. Cần gắn status/
header evidence để phân biệt chắc chắn 429 với timeout/5xx.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 800 |
| Current RPS tại thời điểm chụp | 148.6 |
| Current failures | 0% trên header Locust; checkout current failures khoảng 0.2/s trong bảng endpoint |
| Node count | 7 |
| Current RPS/node tại thời điểm chụp | 21.23 |
| Frontend replicas | 5 |
| Frontend HPA CPU | 67% / target 65% |
| Frontend-proxy replicas | 4 |
| Frontend-proxy HPA CPU | 58% / target 65% |
| Product-catalog replicas / HPA CPU | 6 / 66% trên target 65% |
| Recommendation replicas / HPA CPU | 3 / 45% trên target 65% |
| Frontend pod CPU | 141m, 140m, 127m, 157m, 129m |
| Frontend-proxy pod CPU | 19m, 8m, 46m, 41m |
| Node CPU cao nhất | 80% |
| Browse success rolling 1h | mean 99.9%, min 97.9% |
| Cart success rolling 1h | 100% |
| Checkout success rolling 1h | mean 100%, min 99.9% |
| Browse request rate | max khoảng 157 req/s |
| Browse error request rate | mean 0.770 req/s, max 3.23 req/s |
| Browse latency rolling 1h | p95 mean 77.5 ms, max 440 ms; p99 mean 144 ms, max 729 ms |
| Cart latency rolling 1h | p95 mean 37.4 ms, max 159 ms; p99 mean khoảng 127 ms, max 591 ms |
| Checkout latency rolling 1h | p95 mean 218 ms, max 973 ms; p99 mean 323 ms, max 1.30 s |
| Pod Pending / OOM / restart mới | không quan sát thấy trong output đã cung cấp |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS |
|---|---:|---:|---:|---:|---:|
| `GET /` | 6,226 | 1 | 1,100 ms | 2,000 ms | 4.4 |
| `GET /api/cart` | 16,086 | 2 | 620 ms | 1,300 ms | 11.3 |
| `POST /api/cart` | 32,231 | 3 | 480 ms | 1,200 ms | 24.7 |
| `POST /api/checkout` | 10,799 | 20 | 1,000 ms | 1,700 ms | 7.8 |

Đánh giá:

- Đây là bằng chứng graceful degradation rõ nhất của run về mặt phân bổ
  availability: browse success tụt xuống 97.9% và error rate tăng 3.23 req/s,
  trong khi cart giữ 100% và checkout giữ tối thiểu khoảng 99.9%.
- Hệ không collapse: 7 node giữ nguyên, không thấy OOM/restart, các HPA tiếp
  tục scale pod trên cùng hạ tầng.
- Không mô tả checkout là “bình thường” về hiệu năng: Locust checkout p99
  1,700 ms và Grafana p99 max 1.30 s đều vượt xa target 300 ms. Kết luận đúng
  là checkout được bảo vệ về availability/correctness tốt hơn browse nhưng
  latency đã degraded.
- Throughput có dấu hiệu plateau: tăng từ 700 lên 800 users nhưng current RPS
  chỉ từ 147.1 lên 148.6. Đây là vùng ceiling ứng viên khoảng 149 RPS theo
  snapshot, nhưng ceiling giữ SLO đã bị vượt từ các stage thấp hơn.
- Frontend-proxy đã scale lên 4 replica, làm aggregate token budget động tăng
  lên khoảng 200 RPS. Browse error bắt đầu trước/đồng thời quá trình scale có
  thể do bucket per-proxy bị cạn không đều hoặc do downstream latency. Cần
  response status/header và Envoy counters để quy lỗi cho rate limiter.
- Điều kiện chốt graceful-degradation PASS:
  browse error phải là HTTP 429 có `x-techx-load-shed: browse` và
  `x-envoy-ratelimited: true`; `/api/cart`, `/api/checkout` và product detail
  phải có 429 bằng 0; unexpected 5xx/timeout không tăng.
- `148.6 / 7 = 21.23 RPS/node` là density snapshot, chưa phải sustained
  density canonical.

#### Stage 900 users — preferential degradation rất rõ

**Trạng thái:** PASS mạnh về ưu tiên browse-vs-checkout và chống collapse;
FAIL về latency và overall SLO. Người dùng vẫn checkout được, nhưng protected
flow đã có một lượng lỗi nhỏ nên không mô tả là hoàn toàn không suy giảm.

| Chỉ số | Kết quả ghi nhận |
|---|---:|
| Offered users | 900 |
| Current RPS tại thời điểm chụp | 151.5 |
| Overall current failures | 1% |
| Node count | chưa có snapshot riêng ở stage 900; người chạy xác nhận giữ như stage 800 |
| Browse success rolling 24h | 99.5441% |
| Browse success rolling 1h | mean 99.6%, min khoảng 91.4% |
| Cart success rolling 24h | 100% |
| Checkout success rolling 24h | 99.9814% |
| Browse request rate | max khoảng 167 req/s |
| Browse error request rate | mean 3.21 req/s, max 14.4 req/s |
| Browse latency rolling 1h | p95 mean 108 ms, max 691 ms; p99 mean 179 ms, max 781 ms |

Locust endpoint snapshot:

| Endpoint | Requests | Fails | p95 | p99 | Current RPS | Current failures/s |
|---|---:|---:|---:|---:|---:|---:|
| `GET /` | 6,601 | 1 | 1,200 ms | 2,000 ms | 5.6 | 0 |
| `GET /api/cart` | 17,099 | 2 | 760 ms | 1,400 ms | 13.7 | 0 |
| `POST /api/cart` | 34,187 | 3 | 630 ms | 1,300 ms | 23.8 | 0 |
| `POST /api/checkout` | 11,417 | 34 | 1,200 ms | khoảng 1,900 ms | 5.9 | 0.4 |

Đánh giá:

- Browse là luồng bị hy sinh rõ rệt: success trend xuống khoảng 91.4% và error
  rate lên 14.4 req/s. Cart vẫn giữ 100% và checkout rolling 24h giữ 99.9814%,
  phù hợp với mục tiêu ưu tiên luồng doanh thu.
- Hệ không collapse và người dùng vẫn có thể checkout, nhưng Locust đã ghi
  34 checkout failures và 0.4 failure/s tại thời điểm chụp. Cần phân loại lỗi
  để loại trừ protected-route 429 và unexpected 5xx/timeout.
- Checkout/cart không còn giữ latency SLO: checkout p95 khoảng 1,200 ms và p99
  khoảng 1,900 ms; cart p99 1,300–1,400 ms.
- Throughput tiếp tục plateau: 800 users là 148.6 RPS, 900 users là 151.5 RPS.
  Tăng 100 users chỉ tăng khoảng 2.9 RPS, xác nhận hệ đã ở vùng throughput
  ceiling về served RPS.
- Evidence này chứng minh preferential degradation bằng metric. Để chốt cơ chế
  rate-limit thay vì lỗi tự nhiên do overload, vẫn phải gắn HTTP 429/header
  sample hoặc Envoy `browse_rate_limiter` counters.
- Không có output node/HPA riêng đi kèm stage 900. Claim node không đổi cần
  được củng cố bằng node-set hash sau run, không chỉ dựa trên xác nhận thủ công.

### 5.5. Phân tích canonical từ Locust HTML

Artifact HTML được tạo cho run:

```text
Start:    2026-07-29T04:37:25Z
End:      2026-07-29T15:08:11Z
Duration: 10 giờ 30 phút 46 giây
Host:     http://frontend-proxy:8080
```

#### 5.5.1. Stage history từ dữ liệu nhúng

| Users | Thời lượng ghi nhận | Average RPS | Max RPS | Average failures/s | Max failures/s | Average aggregate p95 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | khoảng 8 giờ 55 phút | 2.10 | 5.7 | 0.0002 | 0.3 | 49.7 ms |
| 300 | 3 phút 23 giây | 63.25 | 86.4 | 0 | 0 | 234.8 ms |
| 350 | 2 phút 55 giây | 71.20 | 79.2 | 0 | 0 | 193.4 ms |
| 400 | 2 phút 59 giây | 81.97 | 89.3 | 0.0111 | 0.1 | 288.9 ms |
| 410 | 4 phút 05 giây | 82.89 | 95.5 | 0.0163 | 0.2 | 337.6 ms |
| 500 | 2 phút 47 giây | 100.32 | 112.5 | 0.0312 | 0.3 | 616.2 ms |
| 600 | 2 phút 44 giây | 118.39 | 128.9 | 0.2061 | 1.0 | 863.3 ms |
| 700 | 2 phút 31 giây | 129.22 | 158.3 | 1.5833 | 7.0 | 1,235 ms |
| 800 | 2 phút 38 giây | 137.90 | 162.4 | 6.5065 | 18.4 | 1,638.1 ms |
| 900 | 59 giây | 136.25 | 164.4 | 13.125 | 29.5 | 2,733.3 ms |

Kết luận từ history:

- Served throughput plateau ở khoảng 138 RPS average khi tăng từ 800 lên
  900 users; average RPS thậm chí giảm từ 137.90 xuống 136.25.
- Error rate và p95 tăng mạnh sau 600 users.
- Không stage 300–900 nào được giữ đủ 5 phút. Vì vậy run này hữu ích để tìm
  vùng breakpoint/overload nhưng chưa đủ làm canonical after benchmark theo
  protocol đã ghi ở mục 6.
- 300 users là highest-passing candidate và 350 users là failing candidate
  theo checkout p99 từ ảnh stage; cần rerun 300/325/350 mỗi stage đủ 5 phút
  để xác định exact ceiling.

#### 5.5.2. Tổng hợp toàn bộ run

| Chỉ số | Kết quả |
|---|---:|
| Total requests | 454,136 |
| Total failures | 2,625 |
| Failure ratio toàn run | khoảng 0.578% |
| Aggregate median | 15 ms |
| Aggregate average | 133.58 ms |
| Aggregate p95 | 850 ms |
| Aggregate p99 | 1,700 ms |
| Aggregate max | 5,754 ms |

Các endpoint lõi trên toàn report:

| Endpoint | Requests | Failures | Failure ratio | p95 | p99 |
|---|---:|---:|---:|---:|---:|
| `GET /` | 13,115 | 3 | 0.023% | 980 ms | 2,000 ms |
| `GET /api/cart` | 36,642 | 5 | 0.014% | 640 ms | 1,500 ms |
| `POST /api/cart` | 73,481 | 8 | 0.011% | 560 ms | 1,500 ms |
| `POST /api/checkout` | 24,614 | 71 | 0.288% | 1,100 ms | 2,200 ms |

#### 5.5.3. Phân loại failures

Locust HTML ghi nhận:

```text
HTTP 500: 2,342
HTTP 503:   283
HTTP 429:     0
```

Các lỗi đáng chú ý:

- `POST /api/checkout`: 69 HTTP 500 và 2 HTTP 503.
- `POST /api/cart`: 8 HTTP 503.
- `GET /api/cart`: 5 HTTP 503.
- `GET /`: 3 HTTP 503.
- Product-detail routes có số lượng HTTP 500 lớn; riêng từng product ID ghi
  nhận khoảng 207–262 lỗi.

Điều này thay đổi kết luận load-shedding:

- Metric Grafana chứng minh browse suy giảm mạnh hơn cart/checkout và hệ không
  collapse, nên preferential containment là có thật.
- Artifact Locust **không chứng minh Envoy rate-limit 429**. Không có HTTP 429;
  các failure ghi trong HTML là unexpected 500/503.
- Vì product detail và checkout là protected routes nhưng vẫn có 500/503,
  reliability gate hiện chưa PASS hoàn toàn.
- Không được dùng các error này làm bằng chứng `x-techx-load-shed`; cần một
  browse-only overload riêng và capture 429/header/Envoy counter.

HTML còn ghi 8 Locust exceptions tại task `flood_home` do biến
`flag_evaluation` chưa được gán khi OpenFeature evaluation lỗi. Đây là lỗi của
load generator/test harness cần được loại trừ hoặc ghi chú khi rerun; không sửa
flagd theo ràng buộc directive.

### 5.6. Canonical after image evidence — fixed 7-node run

These are the newer after-run screenshots supplied for the canonical sequence.
The node panel at the 350-user checkpoint shows `Mean: 7, Max: 7`, consistent
with the operator record that the run stayed at 7 nodes. The image itself is a
`Last 1 hour` panel and therefore directly proves node invariance only for its
visible time window, not the complete 10-hour Locust HTML history.

| Stage | Locust current RPS | Current failures | Browse p95 / p99 | Checkout p95 / p99 | Image-grounded result |
|---:|---:|---:|---:|---:|---|
| 10 | 2.0 | 0% | 20 / 40 ms | 85 / 170 ms | SLO pass at screenshot |
| 300 | 64.0 | 0% | 610 / 1,300 ms | 100 / 230 ms | Pass candidate: browse p95 <1,000 ms; checkout p99 <300 ms |
| 350 | 70.5 | 0% | 590 / 1,300 ms | 130 / 350 ms | First observed checkout-p99 breach; failing candidate |
| 400 | 78.6 | 0% | 600 / 1,200 ms | 180 / 490 ms | Clear checkout-p99 failure |

The Locust request counts and percentiles shown in these screenshots are
cumulative because the same Locust process was not reset between stages. They
are valid point-in-time observations, but not isolated five-minute stage
exports. The Grafana screenshots are rolling 1-hour/24-hour panels and must not
be described as exact-window stage statistics.

Additional values visible in the new images:

- Browse rolling-1h success is 100% at 10/300/350/400; the rolling-24h gauges
  are 99.7274%, 99.7275%, 99.7290% and 99.7302%.
- Cart rolling-1h success is 100% in every supplied stage image.
- Checkout rolling-1h success is 100%; the rolling-24h gauges are 99.9831%,
  99.9831%, 99.9832% and 99.9833%.
- At 300 users, the checkout dashboard p99 is mean 110 ms / max 553 ms; at
  350 users it is mean 124 ms / max 553 ms. These are rolling-window values,
  while the Locust cumulative p99 values are 230 ms and 350 ms respectively.
- No new image shows an HTTP 429 response, the
  `x-techx-load-shed: browse` header, the `x-envoy-ratelimited: true` header or
  an Envoy rate-limit counter.

![Canonical after — 10 users, Locust](../tests/kyverno/mandate-19/test_slo_after/locust-10-user.jpg)

![Canonical after — 10 users, SLO dashboard](../tests/kyverno/mandate-19/test_slo_after/slo-10-user.jpg)

![Canonical after — 10 users, SLO dashboard detail](../tests/kyverno/mandate-19/test_slo_after/slo-10-user-2.jpg)

![Canonical after — 300 users, Locust](../tests/kyverno/mandate-19/test_slo_after/locust-300-user.jpg)

![Canonical after — 300 users, SLO dashboard](../tests/kyverno/mandate-19/test_slo_after/slo-300-user.jpg)

![Canonical after — 300 users, SLO dashboard detail](../tests/kyverno/mandate-19/test_slo_after/slo-300-user-2.jpg)

![Canonical after — 350 users, Locust](../tests/kyverno/mandate-19/test_slo_after/locust-350-user.jpg)

![Canonical after — 350 users, SLO dashboard](../tests/kyverno/mandate-19/test_slo_after/slo-350-user.jpg)

![Canonical after — 350 users, SLO dashboard detail](../tests/kyverno/mandate-19/test_slo_after/slo-350-user-2.jpg)

![Canonical after — node count at 350 users: mean 7, max 7](../tests/kyverno/mandate-19/test_slo_after/node-350-user.jpg)

![Canonical after — 400 users, Locust](../tests/kyverno/mandate-19/test_slo_after/locust-400-user.jpg)

![Canonical after — 400 users, SLO dashboard](../tests/kyverno/mandate-19/test_slo_after/slo-400-user.jpg)

### 5.7. Historical image evidence index

Các ảnh evidence hiện có trong repo được nhúng đầy đủ dưới đây. Chúng là bản
snapshot của run PM-152 cũ; riêng `nodes.jpg`/`node1.jpg` hiển thị burst
9→10→11 node và vì vậy **không** được dùng để phủ nhận run canonical mới mà
người chạy xác nhận giữ 7 node. Run 7-node mới cần lưu thêm node-set
before/after hash nếu mentor yêu cầu kiểm chứng độc lập.

#### Node and dashboard evidence

![Node count — superseded 9→10→11-node run](evidence/mandate-19/pm-152/test_slo/nodes.jpg)

![Node count detail — superseded run](evidence/mandate-19/pm-152/test_slo/node1.jpg)

![Grafana dashboard](evidence/mandate-19/pm-152/test_slo/grafana.jpg)

![Locust transition view](evidence/mandate-19/pm-152/test_slo/Locust_tran.jpg)

#### Stage screenshots

![20 users](evidence/mandate-19/pm-152/test_slo/20_user.jpg)

![100 users — Grafana](evidence/mandate-19/pm-152/test_slo/100_user.jpg)

![100 users — Locust](evidence/mandate-19/pm-152/test_slo/100_user_locust.jpg)

![150 users — Grafana](evidence/mandate-19/pm-152/test_slo/150_user.jpg)

![150 users — Locust](evidence/mandate-19/pm-152/test_slo/150_user_locust.jpg)

![175 users — Grafana](evidence/mandate-19/pm-152/test_slo/175_user.jpg)

![175 users — Locust](evidence/mandate-19/pm-152/test_slo/175_user_locust.jpg)

![200 users — Grafana](evidence/mandate-19/pm-152/test_slo/200_user.jpg)

![200 users — Locust](evidence/mandate-19/pm-152/test_slo/200_user_locust.jpg)

![225 users — Grafana](evidence/mandate-19/pm-152/test_slo/225_user.jpg)

![225 users — Locust](evidence/mandate-19/pm-152/test_slo/225_user_locust.jpg)

![250 users — Grafana](evidence/mandate-19/pm-152/test_slo/250_user.jpg)

![250 users — Locust](evidence/mandate-19/pm-152/test_slo/250_user_locust.jpg)

![275 users — Grafana](evidence/mandate-19/pm-152/test_slo/275_user.jpg)

![275 users — Locust](evidence/mandate-19/pm-152/test_slo/275_user_locust.jpg)

![300 users — Grafana](evidence/mandate-19/pm-152/test_slo/300_user.jpg)

![300 users — Locust](evidence/mandate-19/pm-152/test_slo/300_user_locust.jpg)

![325 users — Grafana](evidence/mandate-19/pm-152/test_slo/325_user.jpg)

![325 users — Locust](evidence/mandate-19/pm-152/test_slo/325_user_locust.jpg)

![350 users — Grafana](evidence/mandate-19/pm-152/test_slo/350_user.jpg)

![350 users — Locust](evidence/mandate-19/pm-152/test_slo/350_user_locust.jpg)

![400 users — Grafana](evidence/mandate-19/pm-152/test_slo/400_user.jpg)

![400 users — Locust](evidence/mandate-19/pm-152/test_slo/400_user_locust.jpg)

![425 users — Grafana](evidence/mandate-19/pm-152/test_slo/425_user.jpg)

![425 users — Grafana detail](evidence/mandate-19/pm-152/test_slo/425_user_01.jpg)

---

## 6. Kế hoạch test after

After run chỉ hợp lệ nếu giữ đúng cùng hạ tầng và cùng profile tải để so với before.

### 6.1. Điều kiện trước khi chạy

- Chốt Git SHA, image digest `frontend` và `frontend-proxy`
- Chụp node-set hash trước run
- Xác nhận không thay NodePool/Karpenter config trong cửa sổ benchmark
- Xác nhận load profile cố định, không đổi transaction mix giữa các stage
- Xác nhận shadow hoặc enforce stage đang ở đúng mức cần test

### 6.2. Kịch bản breakpoint after

Chạy tăng tải theo stage giống protocol before. Không thay đổi node pool,
image digest, workload mix hoặc thời lượng stage giữa before và after.

#### 6.2.1. Chuẩn bị cửa sổ test và snapshot

```bash
export NS=techx-tf3
export RUN_ID=mandate19-after-$(date -u +%Y%m%dT%H%M%SZ)
export OUT="docs/evidence/mandate-19/$RUN_ID"
mkdir -p "$OUT"

kubectl -n "$NS" get nodes -o wide | tee "$OUT/nodes-before.txt"
kubectl -n "$NS" get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' \
  | sort | sha256sum | tee "$OUT/node-set-before.sha256"
kubectl -n "$NS" get hpa -o yaml | tee "$OUT/hpa-before.yaml"
kubectl -n "$NS" get deploy frontend frontend-proxy -o yaml \
  | tee "$OUT/frontend-deploy-before.yaml"
kubectl -n "$NS" top nodes | tee "$OUT/node-usage-before.txt"
kubectl -n "$NS" top pods | tee "$OUT/pod-usage-before.txt"
```

Ghi lại Git SHA, image digest, số node Ready, allocatable CPU và replica hiện
tại. Nếu node-set thay đổi trong lúc benchmark thì đánh dấu run không hợp lệ.

#### 6.2.2. Xác nhận route và enforcement trước khi bắn tải

Lấy endpoint public của storefront vào biến `BASE_URL`. Không dùng endpoint
admin Envoy cho traffic người dùng.

```bash
export BASE_URL="https://<storefront-public-host>"

for path in /api/checkout /api/cart /api/products/OLJCESPC7Z / /api/products; do
  echo "=== $path ==="
  curl -sS -D - -o /dev/null "$BASE_URL$path" \
    | grep -Ei 'HTTP/|x-techx-load-shed|x-envoy-ratelimited'
done

kubectl -n "$NS" get deploy frontend-proxy \
  -o jsonpath='{range .spec.template.spec.containers[0].env[*]}{.name}={.value}{"\n"}{end}' \
  | grep -E 'BROWSE_RATE_LIMIT_(ENABLED|ENFORCED)_PERCENT'
```

Kỳ vọng sau khi rollout config mới: `ENABLED=100`, `ENFORCED=100`; protected
routes không trả 429 ở tải bình thường.

#### 6.2.3. Tăng tải breakpoint theo từng stage

Dùng đúng Locust file và transaction mix đã dùng cho before. Chạy warm-up
30 giây trước mỗi stage, sau đó giữ stage tối thiểu 5 phút. Ví dụ với
Locust CLI:

```bash
export LOCUSTFILE="locustfile.py"
export HOST="$BASE_URL"

# warm-up
locust -f "$LOCUSTFILE" --headless --host "$HOST" \
  -u 20 -r 5 -t 30s --csv="$OUT/warmup"

# breakpoint stages; chỉ chuyển stage khi stage trước đạt gate
for users in 50 100 150 200 250 300 325 350 400 410; do
  locust -f "$LOCUSTFILE" --headless --host "$HOST" \
    -u "$users" -r 10 -t 5m --csv="$OUT/users-$users" \
    --html="$OUT/users-$users.html"
done
```

Nếu load generator dùng URL khác hoặc task file khác, thay `LOCUSTFILE` và
`HOST`, nhưng không thay đổi các stage/transaction mix khi so sánh. Stage đạt
SLO phải có checkout success >=99%, checkout p99 trong SLO, 5xx/timeout không
tăng bất thường, không OOM/restart/pending. Stage đầu tiên vi phạm một gate là
failing stage; stage đạt cuối cùng là highest passing stage.

Trong từng stage, chạy song song các snapshot sau:

```bash
kubectl -n "$NS" get hpa | tee "$OUT/hpa-$users.txt"
kubectl top nodes | tee "$OUT/node-usage-$users.txt"
kubectl -n "$NS" top pods | tee "$OUT/pod-usage-$users.txt"
kubectl -n "$NS" get pods -o wide | tee "$OUT/pods-$users.txt"
```

Lấy RPS, p95/p99, lỗi theo endpoint từ Locust CSV/HTML và dashboard
Prometheus cùng đúng 5 phút của stage. Tính:

```text
requests_per_node = served_rps / count(Ready nodes)
```

#### 6.2.4. Demo graceful degradation khi vượt trần

Sau khi xác định highest passing stage, giữ tải cao hơn stage đó ít nhất
5 phút (ví dụ 410 users). Đồng thời gửi request lặp để chứng minh route:

```bash
for i in $(seq 1 100); do
  curl -sS -D - -o /dev/null "$BASE_URL/" \
    | grep -Ei 'HTTP/|x-techx-load-shed|x-envoy-ratelimited'
done | tee "$OUT/browse-429-sample.txt"

for path in /api/checkout /api/cart /api/products/OLJCESPC7Z; do
  for i in $(seq 1 50); do
    curl -sS -D - -o /dev/null "$BASE_URL$path"
  done | grep -Ei 'HTTP/|x-techx-load-shed|x-envoy-ratelimited' \
    | tee "$OUT/protected-${path//\//_}-sample.txt"
done
```

Kỳ vọng: browse (`/`, `/api/products`) có `HTTP/1.1 429`,
`x-techx-load-shed: browse`, `x-envoy-ratelimited: true`; checkout, cart và
product detail không có 429, checkout success vẫn >=99%, hệ thống không
CrashLoop/OOM/Pending bất thường.

#### 6.2.5. Envoy counters và recovery

```bash
PROXY_POD=$(kubectl -n "$NS" get pod \
  -l app.kubernetes.io/component=frontend-proxy \
  -o jsonpath='{.items[0].metadata.name}')
kubectl -n "$NS" exec "$PROXY_POD" -c frontend-proxy -- \
  wget -qO- localhost:10000/stats \
  | grep -E 'browse_rate_limiter|local_rate_limiter' \
  | tee "$OUT/envoy-counters.txt"

kubectl -n "$NS" get pods -o wide | tee "$OUT/pods-after-load.txt"
kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -n 80 \
  | tee "$OUT/events-after-load.txt"
```

Hạ tải về 0 trong 5 phút, xác nhận p99/error/replica trở về baseline và
không có restart mới. Chỉ sau bước recovery mới kết luận run hợp lệ.

### 6.3. Kịch bản graceful degradation

Sau khi có trần mới:

1. Tính budget browse từ trần mới.
2. Cấu hình token bucket theo `safe_browse_cap / minimum_ready_proxy_count`.
3. Đẩy tải vượt trần trong tối thiểu 5 phút.
4. Xác nhận browse bị shed có chủ đích.
5. Xác nhận checkout/cart vẫn được bảo vệ và hệ không sập toàn bộ.

---

## 7. Khi chạy test cần thu thập gì

Đây là checklist tối thiểu để sau test có thể điền phần after và nộp mentor.

### 7.1. Locust

- offered users từng stage
- current RPS / served RPS
- failure rate
- endpoint-level stats
- raw CSV hoặc HTML report

### 7.2. Prometheus / Grafana

- `frontend` CPU usage
- CPU throttling nếu có
- `frontend-proxy` request rate / pending / upstream pressure
- p95/p99 của browse, cart, checkout theo exact window
- error rate / 5xx / timeout
- HPA target, current utilization, desired replicas, current replicas

### 7.3. Kubernetes / capacity

- node count trước/sau
- node-set hash trước/sau
- pod ready count theo stage
- pod pending / unschedulable events
- restart / OOMKilled / CrashLoopBackOff
- `kubectl top pod` cho hot path

### 7.4. Envoy / load shedding

- `browse_rate_limiter.rate_limited`
- `browse_rate_limiter.enforced`
- response 429 có header:
  - `x-techx-load-shed: browse`
  - `x-envoy-ratelimited: true`

### 7.5. Trace / bottleneck proof

- 1 trace checkout thành công dưới overload
- 1 trace browse bị shed
- proof rằng service bão hòa sớm nhất sau tuning là gì

---

## 8. Điều kiện PASS của Mandate #19

Mandate #19 chỉ nên chốt PASS khi đủ cả 4 nhóm sau:

| Yêu cầu directive | Cần có | Trạng thái hiện tại |
|---|---|---|
| Tìm trần thật | before và after breakpoint có exact số liệu | ⚠️ before đã chốt; after 7-node exploratory có breakpoint candidate nhưng stage chưa đủ 5 phút |
| Nâng trần không thêm node | served RPS và requests-per-node tăng, node count không đổi | ⚠️ after giữ 7 node; RPS/density thấp hơn before 9-node baseline |
| Xử bottleneck | chỉ ra service bão hòa sớm nhất và tuning đã nới nó | ✅ frontend bottleneck đã xác định và HPA/CPU tuning đã triển khai; pressure chuyển sang downstream |
| Xuống mềm khi vượt trần | browse shed, checkout vẫn được bảo vệ, hệ không sập | ⚠️ containment có thật, nhưng chưa có HTTP 429/header/counter để xác nhận Envoy shedding |

---

## 9. Ghi chú trung thực về kết quả after

- Repo hiện đã có nền tảng code/config để giải bài Mandate #19.
- Before breakpoint đã có và đã chỉ ra bottleneck cũ là `frontend CPU saturation and throttling`.
- Đã có after exploratory run và Locust HTML, nhưng chưa thể tuyên bố PASS:
  các stage chưa giữ đủ 5 phút, ceiling giữ SLO chưa tăng so với before và
  failures là HTTP 500/503 thay vì rate-limit 429.
- Cần rerun exact-window quanh 300–350 users và chạy browse-only overload để
  capture 429/header trước khi cập nhật kết luận cuối.

---

## 10. Tài liệu liên quan

| Tài liệu | Nội dung |
|---|---|
| [`docs/adr/0011-mandate-19-throughput-ceiling-load-shedding.md`](adr/0011-mandate-19-throughput-ceiling-load-shedding.md) | ADR: quyết định route classification và load shedding |
| [`docs/mandate-19-implement-plan.md`](mandate-19-implement-plan.md) | kế hoạch triển khai PM-152/153/154 |
| [`docs/runbooks/mandate-19-staged-rollout.md`](runbooks/mandate-19-staged-rollout.md) | rollout staged để giảm rủi ro |
| [`docs/evidence/mandate-19/pm-152/`](evidence/mandate-19/pm-152/) | evidence before breakpoint |
| [`docs/evidence/mandate-19/after-run-template.md`](evidence/mandate-19/after-run-template.md) | checklist đánh giá run after |

---

## 11. Kết luận và trạng thái nộp

Mandate #19 hiện có một exploratory after run trên 7 node, chứng minh hệ không
collapse tới 900 users và HPA tăng pod trên cùng node set. Tuy nhiên run cũng
cho thấy checkout latency vượt SLO từ vùng 350 users, throughput plateau khoảng
138 RPS average ở 800–900 users, và Locust ghi unexpected HTTP 500/503 nhưng
không có HTTP 429. Vì vậy chưa thể chốt Mandate PASS. Việc còn lại là chạy lại
exact-window tối thiểu 5 phút quanh 300–350 users để chốt ceiling giữ SLO, đối
chiếu node-set hash, và chạy browse-only overload để chứng minh 429 có hai
header load-shedding trong khi protected routes có 429 bằng 0.

---

*Ký: CDO01 — 29/07/2026*  
*Liên quan: Directive #19 · ADR 0011 · PM-152 · PM-153 · PM-154*
