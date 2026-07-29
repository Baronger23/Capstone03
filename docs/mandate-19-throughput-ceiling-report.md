# Mandate #19 — Báo cáo triển khai: Biết trần của mình và nâng trần bằng hiệu suất

**Ngày thực hiện:** 23–29/07/2026  
**Người thực hiện:** CDO01  
**Trụ:** Performance Efficiency · chạm Cost Optimization · Reliability  
**Trạng thái:** Draft evidence report — before đã có, after chờ chạy test hoàn tất  
**ADR:** [`docs/adr/0011-mandate-19-throughput-ceiling-load-shedding.md`](adr/0011-mandate-19-throughput-ceiling-load-shedding.md)  
**Runbook rollout:** [`docs/runbooks/mandate-19-staged-rollout.md`](runbooks/mandate-19-staged-rollout.md)  
**Kế hoạch triển khai:** [`docs/mandate-19-implement-plan.md`](mandate-19-implement-plan.md)  
**Evidence before:** [`docs/evidence/mandate-19/pm-152/`](evidence/mandate-19/pm-152/)  
**Evidence after template:** [`docs/evidence/mandate-19/after-run-template.md`](evidence/mandate-19/after-run-template.md)

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
| PM-153 — Throughput tuning | Nâng trần bằng tuning trên cùng node set | ⏳ Code đã chuẩn bị, chờ after run |
| PM-154 — Load shedding | Shed browse, bảo vệ cart/checkout khi overload | ⏳ Shadow/enforcement rollout theo stage |

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
| Highest passing stage | 328 users |
| Failing stage | 410 users |
| Sustained served RPS giữ SLO | 174.75 |
| Breakpoint served RPS | 168.9 |
| Bottleneck sớm nhất | frontend CPU saturation and throttling |
| Co-bottleneck loại trừ được | frontend-proxy chưa overflow; DB pool product-catalog chưa cạn |
| Failure window | 2026-07-26T09:28:30Z → 2026-07-26T09:29:30Z |

### 3.2. Kết luận before

Before run cho thấy hệ chưa gãy vì frontend-proxy hay DB pool. Nút thắt xuất hiện sớm nhất là `frontend` bị bão hòa CPU và bắt đầu throttling. Đây là bottleneck quyết định trần cũ, nên tuning phải tập trung nâng density ở lớp frontend trước.

### 3.3. Density before

| Chỉ số | Before |
|---|---|
| Node count trong run before | _(điền từ node-set before nếu cần trình mentor)_ |
| Served RPS | 174.75 |
| Requests-per-node | _(điền sau khi chốt node count canonical của run before)_ |

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
| Highest passing stage | 328 users | _(điền)_ | _(tính)_ |
| Failing stage | 410 users | _(điền)_ | _(tính)_ |
| Sustained served RPS giữ SLO | 174.75 | _(điền)_ | _(tính)_ |
| Breakpoint served RPS | 168.9 | _(điền)_ | _(tính)_ |
| Primary bottleneck | frontend CPU saturation and throttling | _(điền)_ | _(mô tả)_ |
| Co-bottlenecks | proxy không overflow, DB pool chưa cạn | _(điền)_ | _(mô tả)_ |

### 5.2. Density before/after

| Chỉ số | Before | After | Delta |
|---|---:|---:|---:|
| Fixed node count | _(điền)_ | _(điền, phải bằng before)_ | 0 |
| Served RPS | 174.75 | _(điền)_ | _(tính)_ |
| Requests-per-node | _(điền)_ | _(điền)_ | _(tính %)_ |

**Công thức:**

```text
after_density = after_served_rps / fixed_node_count
improvement_percent = ((after_density / before_density) - 1) * 100
```

### 5.3. Graceful degradation after

| Kiểm tra | Kỳ vọng | After |
|---|---|---|
| Browse overload | có 429 có chủ đích | _(điền)_ |
| Header `x-techx-load-shed: browse` | xuất hiện | _(điền)_ |
| Header `x-envoy-ratelimited: true` | xuất hiện | _(điền)_ |
| Checkout 429 | bằng 0 | _(điền)_ |
| Cart 429 | bằng 0 | _(điền)_ |
| Checkout success | >= 99% | _(điền)_ |
| Checkout p99 trong overload | giữ trong SLO | _(điền)_ |
| Node count | không đổi | _(điền)_ |
| OOM / restart / pending bất thường | không có | _(điền)_ |

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
for users in 50 100 150 200 250 300 328 350 375 410; do
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
| Tìm trần thật | before và after breakpoint có exact số liệu | ⏳ before có, after chờ test |
| Nâng trần không thêm node | served RPS và requests-per-node tăng, node count không đổi | ⏳ chờ after test |
| Xử bottleneck | chỉ ra service bão hòa sớm nhất và tuning đã nới nó | ✅ code + before hypothesis có; ⏳ cần after chứng minh |
| Xuống mềm khi vượt trần | browse shed, checkout vẫn được bảo vệ, hệ không sập | ⏳ chờ overload enforce test |

---

## 9. Ghi chú trung thực trước khi chạy after

- Repo hiện đã có nền tảng code/config để giải bài Mandate #19.
- Before breakpoint đã có và đã chỉ ra bottleneck cũ là `frontend CPU saturation and throttling`.
- Report này chưa thể tuyên bố PASS vì chưa có after run hợp lệ.
- Sau khi chạy test, chỉ cần cập nhật lại các bảng ở mục 5, bổ sung artifact path và kết luận cuối.

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

## 11. Kết luận tạm thời

Mandate #19 đang ở trạng thái “sẵn sàng chạy after benchmark”. Before run đã xác định được trần cũ và nút thắt cũ. Code/config hiện tại đã được tách thành hai hướng xử lý đúng với yêu cầu directive: một nhánh nâng throughput trên cùng hạ tầng, một nhánh bảo vệ hệ khi vượt trần bằng graceful degradation. Việc còn lại để chốt PASS là chạy after trên cùng node set, điền lại số liệu density mới, và chứng minh overload được shed đúng ở browse trong khi checkout vẫn sống.

---

*Ký: CDO01 — 29/07/2026*  
*Liên quan: Directive #19 · ADR 0011 · PM-152 · PM-153 · PM-154*
