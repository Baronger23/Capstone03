# ADR 0011 — Mandate #19: Trần thông lượng, mật độ và cơ chế load-shedding

**Trạng thái:** Đã chấp thuận để triển khai
**Xác minh Directive:** CHƯA PASS — các khoảng trống evidence và acceptance gate chưa đạt được ghi rõ bên dưới
**Ngày ra quyết định:** 23/07/2026
**Ngày rà soát evidence:** 30/07/2026
**Chủ sở hữu / người ký:** CDO01 — TF3
**Trụ liên quan:** Performance Efficiency · Cost Optimization · Reliability
**Báo cáo:** [Báo cáo trần thông lượng Mandate #19](../mandate-19-throughput-ceiling-report.md)

## Bối cảnh

Directive #19 yêu cầu TF3:

1. Đo breakpoint thông lượng thật tại thời điểm một SLO đã phê duyệt bắt đầu
   gãy.
2. Nâng trần thông lượng và requests-per-node mà không thêm node.
3. Xác định và nới service bão hòa đầu tiên.
4. Khi vượt trần, chủ động shed traffic browse ít quan trọng hơn để bảo vệ
   cart/checkout và tránh toàn hệ thống sập.

Phép so sánh phải dùng cùng traffic profile và hạ tầng cố định. Thông lượng cao
hơn sẽ không được chấp nhận nếu làm mất correctness, checkout availability hoặc
latency SLO.

## Quyết định

TF3 áp dụng các kiểm soát sau:

1. Tuning năng lực frontend hiện có thay vì thêm node.
2. Dùng HPA để phân bổ thêm workload lên node-set hiện hữu.
3. Dùng headless discovery chỉ công bố frontend pod đã Ready cho
   frontend-proxy.
4. Phân loại route thành nhóm được bảo vệ và nhóm có thể shed.
5. Chỉ áp dụng Envoy local token bucket theo route cho browse traffic có thể
   shed.
6. Chỉ coi before/after là so sánh hợp lệ khi node identity/count, traffic mix,
   thời lượng stage và cửa sổ đánh giá SLO đều được kiểm soát.

## Số liệu trần thông lượng và mật độ

### Trước tuning

| Chỉ số | Kết quả |
|---|---:|
| Stage cao nhất giữ SLO quan sát được | 400 người dùng đồng thời |
| Stage đầu tiên gãy SLO | 410 người dùng đồng thời |
| Current RPS tại ảnh stage giữ SLO | 76.2 RPS |
| Current RPS tại ảnh stage gãy SLO | 73.9 RPS |
| Số node | 9 |
| Mật độ snapshot | 8.47 RPS/node |
| Điểm bão hòa chính | Frontend CPU saturation và throttling |

Hai node snapshot đầu/cuối của before run đều có cùng hash chín node:
`5d2b7b7885fa55fcc97318ff15fc81fe235edd4cbe98894422ee42811ef7ec5d`.

### Sau tuning

| Chỉ số | Kết quả |
|---|---:|
| Ứng viên stage cao nhất giữ SLO | 300 users |
| Ứng viên stage đầu tiên gãy SLO | 350 users |
| Served RPS trung bình tại ứng viên giữ SLO | 63.25 RPS |
| Served RPS trung bình tại ứng viên gãy SLO | 71.20 RPS |
| Current RPS của Locust trong ảnh | 64.0 RPS tại 300; 70.5 tại 350; 78.6 tại 400 |
| Số node | 7 trong cửa sổ ảnh canonical |
| Mật độ tạm tính tại ứng viên giữ SLO | 9.04 RPS/node |
| Checkout p99 | 230 ms tại 300; 350 ms tại 350; 490 ms tại 400 |

Ảnh node mới tại checkpoint 350 users hiển thị `Mean: 7, Max: 7` trong cửa sổ
`Last 1 hour`. Operator record xác nhận các stage sau cũng giữ bảy node, nhưng
chưa có cặp node-set hash bao phủ toàn bộ lịch sử after run.

Stage 300 users chạy khoảng 3 phút 23 giây và stage 350 users chạy khoảng
2 phút 55 giây. Cả hai đều ngắn hơn cửa sổ duy trì tối thiểu 5 phút, do đó mới
là ứng viên breakpoint, chưa phải trần chính xác đã ký xác nhận.

### Quyết định so sánh before/after

| Measure | Before | After |
|---|---:|---:|
| Highest offered users | 400 observed | 410 observed |
| Peak served RPS holding SLO | Not established | Not established |
| Highest current RPS observed | 76.2 at 400 users | 81.8 at 410 users |

`76.2 RPS` và `81.8 RPS` đều là current RPS tại snapshot, không phải sustained
served RPS giữ SLO. Node set của after attempt thay đổi `9 → 10 → 11`, nên
không thể tính hay tuyên bố cải thiện requests-per-node.

Evidence hiện tại vì vậy **không chứng minh** tuning đã nâng trần thông lượng
hoặc density trên cùng node-set. Run cũ có node tăng 9→10→11 đã bị loại và
không được dùng làm evidence cho after run canonical.

## Nút thắt và quyết định tuning

### Nút thắt đã xác định

Trước tuning, frontend CPU là điểm bão hòa sớm nhất đã đo được.
Frontend-proxy không xuất hiện áp lực pending/overflow và DB pool của
product-catalog vẫn dưới giới hạn cấu hình.

Trong after run:

- tại 300 users, frontend đạt 76% so với HPA target 65%;
- HPA tăng frontend từ hai lên ba replica;
- tại 350 users, frontend giảm còn 63%/65%, chứng minh áp lực ban đầu đã
  được nới;
- recommendation sau đó đạt 71%/65%;
- frontend-proxy đạt 62%/65% tại 350 users và 71%/65% tại 400 users;
- product-catalog lần lượt ở 51%/65% và 57%/65% tại hai checkpoint trên.

Tuning đã nới nút thắt frontend ban đầu và làm áp lực dịch sang
recommendation, sau đó đến frontend-proxy. Tuy nhiên, thay đổi này chưa tạo ra
trần giữ SLO cao hơn theo evidence hiện có.

### Tuning đã áp dụng

| Thành phần | Quyết định |
|---|---|
| Frontend resources | CPU request 200m, CPU limit 500m |
| Frontend HPA | min 2, max 8, CPU target 65%, scale-up không có stabilization delay |
| Proxy-to-frontend discovery | `frontend-headless`, chỉ dùng IP của pod đã Ready |
| Năng lực Envoy | `max_requests: 4096` đã được lên kế hoạch nhưng template hiện chỉ có comment và chưa áp dụng circuit breaker; không tính là tuning đã hoàn tất |
| Ràng buộc năng lực | Không thêm node trong quyết định tuning này |

## Quyết định load-shedding

### Phân loại mức ưu tiên route

| Route | Class | Hành vi khi vượt trần |
|---|---|---|
| `/api/checkout` | `checkout_protected` | Không dùng browse bucket |
| `/api/cart` | `cart_protected` | Không dùng browse bucket |
| `/api/products/<id>` | `product_detail_protected` | Được bảo vệ để giữ checkout journey |
| `/` và `/api/products` listing/browse | `browse_shedable` | Có thể chủ động trả HTTP 429 |

Product detail được bảo vệ vì cart/checkout journey phải đọc product trước khi
thay đổi cart. Shed dependency này sẽ làm việc bảo vệ checkout mất ý nghĩa.

### Cơ chế

Envoy `envoy.filters.http.local_ratelimit` được cấu hình theo từng proxy:

```yaml
BROWSE_RATE_LIMIT_MAX_TOKENS: "100"
BROWSE_RATE_LIMIT_TOKENS_PER_FILL: "50"
BROWSE_RATE_LIMIT_FILL_INTERVAL: "1s"
BROWSE_RATE_LIMIT_ENABLED_PERCENT: "100"
BROWSE_RATE_LIMIT_ENFORCED_PERCENT: "100"
```

Response browse bị shed có chủ đích phải là:

```text
HTTP 429
x-techx-load-shed: browse
x-envoy-ratelimited: true
```

Local token bucket tồn tại độc lập trên mỗi proxy. Năng lực browse hiệu dụng
của cluster vì vậy phụ thuộc số frontend-proxy replica đang Ready và phải được
ghi lại trong demo overload.

## Kết quả load-shedding runtime

HTML của after run hiện tại ghi nhận:

| Evidence runtime | Kết quả |
|---|---:|
| HTTP 429 | 0 |
| HTTP 500 | 2,342 |
| HTTP 503 | 283 |
| Capture `x-techx-load-shed: browse` | Chưa có |
| Capture `x-envoy-ratelimited: true` | Chưa có |
| Delta Envoy rate-limit counter | Chưa có |
| Checkout failures | 69 HTTP 500 và 2 HTTP 503 |

Browse suy giảm mạnh hơn cart/checkout và cluster không sập toàn bộ, nhưng đây
không phải bằng chứng load-shedding có chủ đích. Không được đổi nhãn các
phản hồi 500/503 ngoài dự kiến thành shed traffic. Checkout cũng vượt ngưỡng
p99 300 ms từ vùng 350 users.

## Ma trận nghiệm thu Directive

| Yêu cầu Directive | Evidence | Quyết định |
|---|---|---|
| Tìm breakpoint thật | Before đã có số liệu; ứng viên after 300-pass/350-fail đều ngắn hơn 5 phút | MỘT PHẦN |
| Nâng trần không thêm node | RPS và density after thấp hơn; before dùng 9 node, after dùng 7 | FAIL |
| Tìm và nới bottleneck | Đã tìm frontend saturation; HPA scale làm áp lực giảm và dịch xuống downstream | PASS cho hành động tuning |
| Xuống mềm khi vượt trần | Không có 429, header bắt buộc hoặc Envoy counter; xuất hiện 500/503 | FAIL |
| Giữ correctness/reliability | Checkout p99 gãy và checkout trả 500/503 | FAIL |
| Giữ số node cố định | Cửa sổ ảnh 7 node ổn định; thiếu bằng chứng cùng node-set cho before/after | MỘT PHẦN |
| Nộp trước 22/07/2026 | Evidence review và chữ ký ngày 30/07/2026 | FAIL — trễ hạn |

## Evidence cần bổ sung để đóng Directive

1. Chụp hash từ node name/UID/providerID trước, trong và sau cả hai run.
2. Chạy cấu hình before và tuned trên cùng một node-set cố định gồm bảy node.
3. Dùng cùng canonical traffic mix và image digest.
4. Giữ mỗi stage ít nhất 5 phút; xuất Locust CSV và Prometheus exact-window.
5. Chứng minh tuned SLO-holding RPS và RPS/node cao hơn before.
6. Chạy browse overload đồng thời với protected checkout traffic.
7. Ghi lại browse HTTP 429, hai response header bắt buộc và delta Envoy
   `rate_limited`/`enforced` counter.
8. Chứng minh protected-route có 429 bằng 0, checkout success ≥99%, checkout
   p99 trong SLO, không có 5xx/timeout ngoài dự kiến, OOM/restart/Pending pod hoặc
   node change.

## Hệ quả và đánh đổi

- Browse có thể nhận phản hồi 429 có chủ đích khi overload.
- Cart, checkout và product detail được ưu tiên năng lực trước browse.
- Local token bucket tránh thêm network dependency nhưng tổng năng lực thay
  đổi theo số proxy replica.
- Trong mandate này, HPA chỉ được thêm pod trên node hiện hữu; bất kỳ sự kiện
  scale node nào cũng làm phép so sánh không hợp lệ.
- Việc chấp thuận triển khai không đồng nghĩa Directive đã PASS. Evidence
  runtime mới là cơ sở nghiệm thu.

## Ràng buộc được giữ nguyên

- Quyết định này không thay đổi flagd.
- Storefront public và các operational endpoint private tiếp tục tuân theo
  Directive #1.
- Stateful topology và năng lực của Karpenter NodePool nằm ngoài quyết định
  tuning này.

## Tham chiếu

- [Báo cáo trần thông lượng Mandate #19](../mandate-19-throughput-ceiling-report.md)
- [Đánh giá after evidence](../evidence/mandate-19/after/README.md)
- [After evidence template](../evidence/mandate-19/after-run-template.md)
- [Runbook staged rollout](../runbooks/mandate-19-staged-rollout.md)
- `gitops/infrastructure/hpa-hotpath.yaml`
- `phase3 - information/deploy/values-prod.yaml`
- `phase3 - information/techx-corp-platform/src/frontend-proxy/envoy.tmpl.yaml`

---

**Người ký:** CDO01 — TF3
**Ngày ký:** 30/07/2026
**Tuyên bố xác minh:** Quyết định kiến trúc đã được chấp thuận; Directive #19
vẫn CHƯA PASS cho tới khi toàn bộ tiêu chí nghiệm thu bên trên được đáp ứng.
