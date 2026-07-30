# Mandate #19 — Báo cáo: Biết trần của mình và nâng trần bằng hiệu suất

**Ngày đo:** 30/07/2026
**Người thực hiện:** CDO01 — TF3
**Trụ:** Performance Efficiency · chạm Cost Optimization · Reliability
**ADR:** [`docs/adr/0011-mandate-19-throughput-ceiling-load-shedding.md`](adr/0011-mandate-19-throughput-ceiling-load-shedding.md)
**Evidence canonical:** [`docs/evidence/mandate-19/real-2026-07-30/`](evidence/mandate-19/real-2026-07-30/)
**Harness tái lập:** [`scripts/mandate-19/`](../scripts/mandate-19/)

> **Bản này thay thế hoàn toàn báo cáo cũ.** Số liệu cũ (trần "174,75 RPS @ 328 user")
> đã bị loại — lý do ở §2. Mọi con số dưới đây có artifact thô đi kèm và tái lập được
> bằng lệnh.

---

## 1. Directive hỏi gì

| # | Yêu cầu |
|---|---|
| 1 | Tìm trần THẬT — tăng tải tới khi SLO gãy, xác định chính xác chịu được bao nhiêu |
| 2 | Nâng trần **bằng hiệu suất, không thêm node**; chứng minh requests-per-node tăng |
| 3 | Tìm service **bão hoà sớm nhất** (cạn CPU/mem/connection/queue) và nới nó |
| 4 | Vượt trần thì **xuống mềm** — shed browse, giữ checkout, không sập |

---

## 2. Vì sao phải đo lại từ đầu

Bộ evidence cũ (`pm-152/`, `after/`) không dùng được:

| Vấn đề | Chi tiết |
|---|---|
| **Node-set trôi giữa bài** | `pm-152/test_slo/nodes.jpg` cho thấy **9 → 10 → 11** node. Directive đòi "không thêm node" — mọi claim requests-per-node từ đó mất cơ sở. |
| **Stage quá ngắn** | Nhiều stage 59s–4 phút, dưới protocol 5 phút. |
| **Cổng đánh giá không tồn tại** | Tuyên FAIL bằng "checkout p99 ≤ 300ms". Ngưỡng này **không có trong `SLO.md`** — nó là budget server-side steady-state của Mandate #16, bị áp lên p99 **client-side** trong lúc **cố ý** đẩy quá trần. |
| **Không tái lập được** | Trần "174,75 RPS @ 328 user" không có CSV/JSON thô. |

### Cổng SLO dùng trong bản này

Đúng bốn ngưỡng trong [`SLO.md`](../phase3%20-%20information/onboarding/SLO.md), query lấy
nguyên từ `slo-dashboard.json` (chỉ thay `$__rate_interval` bằng độ dài cửa sổ):

| SLI | Ngưỡng |
|---|---|
| Browse non-5xx | ≥ 99,5% |
| Browse p95 | < 1s |
| Cart success | ≥ 99,5% |
| Checkout success | ≥ 99,0% |

**Không có ngưỡng latency cho checkout trong hợp đồng SLO.** Bản này không tự chế thêm.

### Protocol đo

| Hạng mục | Giá trị |
|---|---|
| Thời lượng stage | 420s; **cửa sổ đo = 300s cuối** (bỏ ramp) |
| Generator | **ngoài cluster** (Docker trên máy vận hành), đi qua CloudFront công khai |
| Vì sao ngoài cluster | Generator trong cluster tranh CPU với chính hệ đang đo, và ở tải cao còn kích Karpenter cấp node — đã đo được node trôi **7 → 10** khi bắn tải |
| Profile | port nguyên từ `src/load-generator/locustfile.py`, `wait_time = between(1,10)` |
| Snapshot mỗi stage | `node_count`, `node_set_sha256`, `kubectl get hpa`, `top nodes` → `infra.txt` |

---

## 3. Một lỗi phương pháp đã phải sửa giữa chừng — đọc trước khi xem số

Ban đầu tôi lấy `frontend_total_rate` (span metrics trong Prometheus) làm "served RPS". **Sai.**

Phát hiện ra vì stage 800 user báo throughput **thấp hơn** stage 600 user, trong khi Locust
offered giống hệt. Đối chiếu từng `span_name` thì **mọi route giảm đúng cùng hệ số 1,688×**
— dấu hiệu mất mát đồng đều, không phải hệ chậm đi. Log `otel-gateway`:

```
07:18:01Z memorylimiter  "Memory usage is above soft limit. Forcing a GC."  cur_mem_mib=495
07:18:10Z queue_sender   "Exporting failed. Dropping data."                 dropped_items=8645
07:19:00Z queue_sender   "Exporting failed. Dropping data."                 dropped_items=8365
07:19:18Z queue_sender   "... larger than max 4194304"                      dropped_items=10100
```

**Cách xử:**

| Loại số | Nguồn | Lý do |
|---|---|---|
| Tỉ lệ (success rate, latency) | Prometheus span metrics | mất mát đồng đều → tử/mẫu cùng co → tỉ lệ còn đúng |
| Tuyệt đối (RPS) | **CSV Locust** | đo tại người dùng, không qua pipeline nào |

Script: [`scripts/mandate-19/client_truth.py`](../scripts/mandate-19/client_truth.py).

**Lưu ý khi đọc "RPS":** generator là closed-loop có think time, nên offered RPS bị chặn bởi
*số user / think time* chứ không bởi sức hệ. Vì vậy **trần đọc theo SỐ USER** giữ được SLO;
RPS là con số dẫn xuất báo cáo kèm.

---

## 4. YC#1 — Trần THẬT

Arm `baseline` = cấu hình production trước mọi tuning của mandate này.

| Users | served RPS | browse | cart | checkout | Verdict |
|---:|---:|---:|---:|---:|---|
| 200 | 40,9 | 99,258% | 100% | 99,89% | FAIL¹ |
| 400 | 76,0 | 99,498% | 100% | 100% | ~biên |
| 600 | 121,7 | 99,632% | 100% | 99,96% | PASS |
| 800 | 164,1 | 99,977% | 99,991% | 100% | PASS |
| **1000** | **202,4** | **99,610%** | **100%** | **99,89%** | **PASS ← TRẦN** |
| 1400 | 238,8 | 99,585% | 99,988% | **29,21%** | FAIL |
| 1800 | 298,2 | 99,019% | 99,991% | 7,12% | FAIL |
| 2400 | 342,4 | 84,763% | 99,982% | 0,02% | FAIL |

¹ 200 user FAIL do node-churn thoáng qua (80 lỗi dồn trong 6 giây lúc Karpenter
consolidate node), không do tải. Chi tiết trong `baseline/u200/locust_failures.csv`.

> ### Trần = **1000 user đồng thời · 202,4 RPS phục vụ**
> Cao hơn ~3× con số 328 user trong báo cáo cũ.

**Thứ gãy trước tiên không phải browse mà là CHECKOUT** — rơi thẳng 99,89% → 29,21% chỉ
trong một nấc tải. Browse lúc đó vẫn còn 99,585%.

---

## 5. YC#3 — Nút thắt: ba nguyên nhân, hai trong ba không phải CPU

### 5.1. `email` — bão hoà **hàng đợi**

| Điểm đo (stage 1400 user) | p95 |
|---|---:|
| span **client** `POST` checkout → email | **15 000 ms** = route timeout Envoy |
| span **server** email | **391 ms** |

**14,6 giây chênh lệch là thời gian XẾP HÀNG, không phải xử lý.** Đúng loại bão hoà
directive gọi tên: *"không phải chậm — mà cạn: connection/queue depth"*.

Vì sao nó kéo sập checkout: `checkout` gọi `sendOrderConfirmation` **đồng bộ**
(`src/checkout/main.go:473`), không đặt deadline riêng → hàng đợi email ăn trọn budget
request → **504**. Ở stage vỡ: **3 432/5 431 đơn hỏng = 82% toàn bộ lỗi client**.

Sức chứa: Ruby/Sinatra trên Puma (MRI có GIL), **1 replica**, limit CPU **100m = 0,1 core**,
trong khi tải là 14,7 rps × 391 ms ≈ **5,8 request đồng thời**.

**Nới (PR #656):** HPA 2..8 @60% · request 25m→75m · limit 100m→**600m**.

**Kết quả đo lại — checkout ở stage 1400 user:**

| baseline | tuned (#649) | tuned2 (#656) |
|---:|---:|---:|
| 29,21% | 36,62% | **98,18%** |

### 5.2. Kết nối bị ghim vào một pod — **lý do "thêm replica" không có tác dụng**

`kubectl top pod` khi `product-catalog` đang ở **11 replica**:

```
xxhsp 353m · cw8nx 136m · pzcxg 11m · TÁM pod còn lại 1-2m
```

`product-reviews` y hệt: 313m / 254m / 85m / 4m.

**Cơ chế:** Service ClusterIP trả về **một VIP** → gRPC giữ **một kết nối TCP dài hạn** →
kube-proxy ghim kết nối đó vào **một pod**. Pod do HPA sinh ra *sau* khi kết nối đã dựng
thì **không bao giờ** nhận traffic.

Hệ quả kép: HPA thấy CPU **trung bình 48%** nên ngừng scale, trong khi pod nóng chính là pod
làm vỡ deadline và sinh `HTTP 500` trên `/api/products/[id]`.

**Đối chứng ngay trong cụm:** `frontend` trải đều **123–138m** — vì hop
`frontend-proxy → frontend` đã đi qua `frontend-headless` từ trước. Pattern đúng đã có sẵn
trong repo, chỉ chưa áp cho hop `frontend → backend`.

**Nới (PR #660):** Service headless + `round_robin` phía client. Phải **cả hai vế** —
headless mà giữ `pick_first` thì vẫn ghim IP đầu; `round_robin` mà giữ ClusterIP thì DNS chỉ
trả 1 VIP, không có gì để xoay.

### 5.3. Deadline gRPC 500ms là cò súng quá nhạy

Log frontend ở stage vỡ: `4 DEADLINE_EXCEEDED: Deadline exceeded after 0.500s`.

`product-catalog` p95 server-side chỉ **6,9 ms** — deadline không thấp so với trung vị, nó
quá sát **đuôi**. Không có retry nên timeout thành lỗi cứng: **311 × HTTP 500**
(`/api/products/[id]`) + **431 × HTTP 503** (`/api/product-reviews/[id]`) = 742 lỗi.

Deadline tồn tại là đúng (REL-17-02). Chỉ chỉnh **ngưỡng** 500 → 1200 ms.

### 5.4. Right-size request theo **cả hai chiều**

| Service | Đo được | Hành động |
|---|---|---|
| `accounting` | throttle **86,1%** — consumer MSK **duy nhất** ghi đơn vào RDS | req 50m→150m · limit 200m→600m |
| `recommendation` | throttle 18,1%, nằm trong mẫu số SLI browse | req 100m→150m · limit 500m→700m |
| `ad` | dùng 17–21m nhưng **giữ chỗ 100m**, throttle 0% | req 100m→**30m** (trả chỗ) |

`accounting` throttle 86,1% là phát hiện độc lập đáng lưu ý: throttle ở đó nghĩa là **đơn đã
đặt xong vẫn nằm chờ trong topic**.

---

## 6. YC#2 — Nâng trần: điều KHÔNG hiệu quả và điều hiệu quả

### 6.1. Nới `maxReplicas` một mình: KHÔNG hiệu quả

Arm `tuned` (PR #649): frontend 8→16, checkout 8→14, proxy 8→12, catalog 8→12. Đo lại đủ 8 stage:

| Users | baseline RPS | tuned RPS | Δ |
|---:|---:|---:|---:|
| 1000 (trần) | 202,4 | 202,8 | +0,4 |
| 1400 | 238,8 | 240,2 | +1,4 |

**Trần không đổi — vẫn 1000 user.** Lý do ở §5.2: replica thêm vào là dung lượng
**traffic không tới được**.

Tệ hơn, một mình nó còn **làm yếu lớp shed** (§7.2).

### 6.2. Nới nút thắt `email`: dịch được điểm gãy

Arm `tuned2` (PR #656):

| Users | browse | cart | checkout | Verdict |
|---:|---:|---:|---:|---|
| 800 | 99,635% | 99,991% | 99,95% | PASS |
| **1000** | **99,629%** | **100%** | **99,96%** | **PASS** |
| 1400 | 96,465% | 100% | **98,18%** | FAIL (browse) |

Checkout ở 1400 lên **98,18%** (từ 29,21%) — nút thắt §5.1 đã xử. Nhưng trần vẫn 1000 user
vì **ràng buộc dịch sang browse**, đúng chỗ nút thắt §5.2 nằm.

### 6.3. Trạng thái YC#2

**Chưa đạt.** Trần vẫn 1000 user qua ba arm. Đường đi đã xác định rõ và đã có PR:
`#660` (client-side LB) là thứ chạm đúng nguyên nhân §5.2, nhưng cần rebuild image frontend
nên chưa có số "sau" tại thời điểm viết. Không tuyên PASS khi chưa có số.

### 6.4. Ràng buộc "không thêm node" được tôn trọng

Ở stage vượt trần, pod hot-path ở trạng thái `Pending` với lý do:

```
Failed to schedule pod, node limits have been exhausted for nodepool (flash-sale-spot-arm64);
node limits have been exhausted for nodepool (elastic-ondemand-fallback-arm64)
```

Karpenter `limits` chặn cấp thêm node — đó là bằng chứng ràng buộc còn hiệu lực, không phải sự cố.

---

## 7. YC#4 — Xuống mềm

### 7.1. Cơ chế chạy thật, đo qua đường public

| Kiểm tra | Kết quả |
|---|---|
| `GET /api/products` lúc overload | **7/8 → HTTP/2 429** kèm `x-techx-load-shed: browse` |
| Envoy `browse_rate_limiter` | `rate_limited: 19449` · `enforced: 19449` · `ok: 6221` |
| Bucket bảo vệ luồng tiền | `local_rate_limiter.rate_limited:` **0** |
| `/api/products/<id>`, `/api/cart` lúc overload | **200**, không 429 |

Trong ladder, stage 2400 user (2,4× trần): **3 641 × 429** trên route shedable,
**0 × 429** trên route protected.

**Điểm cần giải thích với mentor:** browse success trên Grafana **không tụt** khi shed hoạt
động. Đúng thiết kế — 429 bị chặn tại Envoy nên không tới frontend, và `SLO.md` định nghĩa
browse SLI là **non-5xx**, mà 429 không phải 5xx. Shed hy sinh browse **mà không đốt SLO**.

**Đính chính:** runbook cũ đòi header `x-envoy-ratelimited: true`. Yêu cầu đó **bất khả thi**
— filter `local_ratelimit` không phát header đó (chỉ filter *global* ratelimit mới có). Bằng
chứng đúng là `x-techx-load-shed: browse`.

### 7.2. Regression do chính chúng tôi gây ra — và bản sửa

Bucket là **per-replica**, nên budget tổng = `tokens_per_fill × số replica proxy`.
PR #649 nới proxy 8 → 12 và vô tình nâng luôn budget shed 400 → 600:

| Arm | proxy max | 429 @2400 user | browse @2400 |
|---|---:|---:|---:|
| baseline | 8 | **3 641** | 84,8% |
| tuned | 12 | **0** | 95,4% |
| tuned2 | 12 | **0** | **63,4%** |

Dòng `tuned2` là bằng chứng rõ nhất: sau khi checkout được nới, tải dồn hết sang browse, và
vì lớp shed **không còn kích hoạt**, browse rơi tự do xuống 63,4% — thấp hơn hẳn baseline
84,8% ở cùng mức tải. **Nhiều replica hơn mà mất khả năng xuống mềm là ngược chiều YC#4.**

**Sửa (PR #658):** `tokens_per_fill` 50 → **33** (12 × 33 = 396 ≈ 8 × 50 = 400 của baseline),
`max_tokens` 100 → 66.

**Hạn chế còn lại:** budget vẫn trôi theo số replica. Sửa đúng về kiến trúc là bucket dùng
chung toàn cluster (`local_cluster_rate_limit`) — nằm trong image, phải rebuild.

---

## 8. Khoảng trống quan sát phát hiện kèm

| Vấn đề | Chi tiết | Ảnh hưởng tới bài này |
|---|---|---|
| **cAdvisor chết 7/8 node** | `Get "https://10.0.x.x:10250/metrics/cadvisor": context deadline exceeded` | Panel *"Pod count — hot-path services"* luôn `No data` → **không dùng làm bằng chứng**. Số per-pod lấy từ metrics-server. |
| **NodePool thiếu `techx.io/arch`** | `label "techx.io/arch" does not have known values (typo of "kubernetes.io/arch"?)` — 10 workload hot path `nodeSelector` vào label mà NodePool không khai báo | Karpenter không cấp được node cho hot path. Mandate #13, CDO01. |
| **SLI checkout từng mù** | Panel SLO đo trên span **nội bộ** checkout → request timeout ở tầng trên vô hình. Ở 2400 user: **8 875/8 877 đơn hỏng** mà dashboard vẫn báo `checkout_success = 100%` | Đã sửa (PR #649): đo ở **biên** frontend. |

---

## 9. Trạng thái theo từng yêu cầu

| YC | Trạng thái | Bằng chứng |
|---|---|---|
| 1. Tìm trần THẬT | ✅ **Đạt** | 1000 user / 202,4 RPS, 8 stage exact-window, node-set hash mỗi stage |
| 2. Nâng trần không thêm node | ❌ **Chưa** | 3 arm đều dừng ở 1000 user. Nguyên nhân đã xác định (§5.2), PR #660 chưa có số sau |
| 3. Xử nút thắt | ✅ **Đạt** cho `email` | checkout @1400: 29,21% → **98,18%**. Hai nút thắt còn lại đã định vị + có PR |
| 4. Xuống mềm | ✅ **Đạt** cơ chế · ⚠️ cần merge #658 | 429 + header + counter Envoy trên đường public; regression budget đã tìm ra và có bản sửa |

---

## 10. Tái lập

```sh
# tunnel EKS + prometheus
kubectl -n techx-tf3 port-forward svc/prometheus 29090:9090

# một stage
bash scripts/mandate-19/run_stage_external.sh <arm> <users> 420 300

# tổng hợp client-side
python3 scripts/mandate-19/client_truth.py <thư-mục-arm>

# demo xuống mềm + video
kubectl -n techx-tf3 port-forward svc/grafana 23000:80
bash scripts/mandate-19/shed_demo.sh <out-dir> 120 420
```

Chi tiết: [`scripts/mandate-19/README.md`](../scripts/mandate-19/README.md).

---

## 11. Việc còn mở

1. Merge #658 (hiệu chỉnh shed) + #660 (client-side LB) → rebuild image frontend → bump digest
   → chạy arm `tuned3` để có số YC#2.
2. Bucket shed dùng chung toàn cluster (`local_cluster_rate_limit`).
3. Sửa cAdvisor 7/8 node.
4. Bổ sung `techx.io/arch` vào `requirements` của NodePool arm64.
5. Bọc timeout riêng cho `checkout → email` để hàng đợi service phụ trợ không ăn được trọn
   budget của luồng tiền.

---

**Ký:** CDO01 — TF3 · 30/07/2026
