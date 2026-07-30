# Mandate #9 — Phân chia công việc & trình tự thực thi (Work Breakdown + Schedule)

**Đội thực thi (4 người):** **Hải** (Lead/Go/integration) · **Đức** (.NET/accounting/schema) ·
**Đông** (Observability/Python) · **Mến** (Security/Infra/MSK/RDS)
**Ngày soạn:** 28/07/2026 · **v2:** 28/07 · **v3:** 29/07 · **v3.1:** 29/07 · **v3.2:** 29/07 ·
**v3.3:** 29/07 · **v3.4:** 29/07 (chuẩn hóa Description/Why/How/Acceptance cho mọi task)
**Đi kèm:** [`mandate-09-zero-downtime-ops-solution.md`](mandate-09-zero-downtime-ops-solution.md) (v3.2).

> ### 🔧 Changelog v3.4
> - Cả **22/22 task** dùng cùng template bắt buộc: **Description → Why → How → Acceptance criteria**.
> - Tách M9-05a/b/c thành ba task đầy đủ, không còn dùng acceptance chung.
> - Bổ sung nội dung thực thi cho M9-09 và M9-16 dù đây là bonus/hardening post-demo.
> - `How` mô tả trình tự thao tác; `Acceptance criteria` chỉ giữ điều kiện PASS/FAIL kiểm chứng được.
>
> ### 🔧 Changelog v3.3
> - Thay role A/B/CDO01 bằng bốn owner thật: **Hải, Đức, Đông, Mến**; reviewer luôn là người khác owner.
> - Bỏ dependency M9-02→M9-01 vì đó chỉ là resource constraint của lịch hai người; catalog/reviews nay chạy
>   song song theo readiness contract đã chốt trong solution.
> - Bốn nhánh khởi động đồng thời ngày **29/07**: catalog · accounting · observability · rotation infra.
> - Chuỗi accounting vẫn tuần tự **M9-03→M9-07d→M9-15a→M9-07i→M9-05a**; các generation reload của
>   catalog/reviews chỉ bắt đầu sau task cache tương ứng và M9-04 để tránh sửa chồng file.
> - Earliest-safe gates: staging-ready **05/08** · rehearsal PASS **10/08** · production W1 **11/08** ·
>   đủ bake + W2 approval **12/08** · production W2/FINAL **13/08**.
> - Lịch mặc định ngày làm việc, mentor/change approver phản hồi đúng gate; phản hồi chậm hoặc gate FAIL làm
>   mốc sau tự động trượt, không rút ngắn rehearsal/bake để giữ ngày.
>
> ### 🔧 Changelog v3.2
> - M9-06 đổi thành **integration/staging-ready ở dormant mode**, tuyệt đối không cutover production trước
>   M9-12; production cutover/rotation chuyển vào M9-13.
> - Tách M9-07 thành **07d design** và **07i implementation**; mentor sign-off M9-15a due 07/08, không còn
>   phụ thuộc task due 10/08 hay rơi vào Thứ Bảy 08/08.
> - Tách approval: M9-15b cho production W1/M9-13 và M9-15c cho destructive CONTRACT W2/M9-14.
> - Chốt contract bảng lớn: `orderitem.created_at SET NOT NULL` sau validated CHECK; M9-14 contract cả
>   `orderitem` và `products` dưới tải.
> - M9-00/M9-13/M9-14 bắt **traffic floor + N theo từng impacted route/store**, không chỉ tổng RPS.
> - Gán **CDO02 lead = B** trong lịch; tính lại effort gồm M9-11/M9-15. Catalog cache dùng canonical snapshot;
>   rotation scope ghi rõ ba app secret/user.
>
> ### 🔧 Changelog v3.1
> - **Replan lịch cho KHẢ THI** (lỗi cũ: M9-04 due 05/08 mà M9-05 3d cũng due 06/08; role CDO02-App ôm 11d
>   trong 1 tuần): tách **M9-05 → 05a/05b/05c**, chuỗi accounting **tuần tự hoá 03→07→05a** (3 task cùng sửa
>   `Consumer`/`DBContext`/entity — không được song song), demo dời **12/08 → 18/08**.
> - **Critical path vẽ lại đúng dependency**: M9-04 KHÔNG phụ thuộc M9-01/02/03 — hai nhánh song song hội tụ
>   ở M9-06.
> - **M9-15 mới:** mentor sign-off + production change approval = **deliverable có Owner/Due riêng** (không
>   còn nằm ẩn trong dependency M9-13).
> - **M9-14 = cửa sổ CONTRACT mentor quan sát dưới tải** (Reviewer: mentor) — đóng khoảng trống compliance
>   "mentor phải xem đủ expand→…→contract".
> - Siết acceptance: M9-03 idempotency chi tiết (ConstraintName, fresh-context compare, so cả aggregate,
>   quarantine/DLQ, key=order_id) · M9-02 pool-exhaustion không chạm customer path · M9-07 SQL (index ngoài
>   txn, dọn invalid index, verify theo watermark, chốt CHECK/NOT NULL) · M9-06 hai loại rollback ·
>   M9-08 `apply_method` · M9-10 client gate.
>
> ⚠️ **Cần mentor duyệt gia hạn** (hạn gốc 19/07 đã qua); M9-15a là hard gate. Lịch tính ngày làm việc,
> bỏ cuối tuần, bắt đầu **Thứ Tư 29/07/2026**. Mentor/change approver là reviewer ngoài team-size 4 người.

---

## 0. Trình tự & đường găng (v3.3 — 4 người, earliest-safe)

```
Hải:  M9-01 ───────────────────────────────→ M9-05b ─┐
Đức:  M9-03 → M9-07d → M9-15a → M9-07i → M9-05a ───┤
Đông: M9-00 → M9-02 ───────────────────────→ M9-05c ─┼→ M9-06 (staging-ready)
Mến:  M9-04 → M9-08 → M9-10 ────────────────────────┘
                                       M9-11 ─────────┐
M9-06 + M9-11 ────────────────────────────────────────┼→ M9-12 → M9-15b → M9-13 (prod W1)
                                                     └→ deploy revision B + bake ≥24h → M9-15c → M9-14 (prod W2)
                                                                                         └→ FINAL
```
- **Bốn nhánh chạy song song từ 29/07**; M9-02 không còn phụ thuộc M9-01 vì khác owner/codebase.
- **Chuỗi accounting tuần tự:** M9-03 → M9-07d → M9-15a → M9-07i → M9-05a.
- M9-05b phụ thuộc M9-01+M9-04; M9-05c phụ thuộc M9-02+M9-04 — vừa đủ dependency kỹ thuật và tránh
  hai người sửa chồng catalog/reviews.
- **M9-06 không đổi production state**; M9-12 mới chạy cutover/rotation staging, M9-13 mới chạy production W1.
- M9-15a ký design sớm; M9-15b và M9-15c là hai production change approval độc lập.

## Lịch tổng hợp (v3.3 — ngày làm việc, bắt đầu Thứ Tư 29/07)

| Task | Việc | Owner | Reviewer | Phụ thuộc | Effort | **Due** |
|---|---|---|---|---|---|---|
| M9-00 | Bộ đo 7 điều kiện + load harness + timeout budget | **Đông** | Hải | — | 1.5d | **30/07 AM** |
| M9-03 | accounting idempotent + checkout producer | **Đức** | Hải | — | 1.5d | **30/07 AM** |
| M9-07d | Schema design/ADR draft + mentor packet | **Đức** | Hải | M9-03 | 0.5d | **30/07 PM** |
| M9-15a | Mentor design sign-off + gia hạn | **Đức** | mentor | M9-07d | 0.25d | **31/07 AM** |
| M9-01 | catalog cache + readiness startup-latch | **Hải** | Đông | — | 2.5d | **31/07 AM** |
| M9-04 | 3 rotation scope + Lambda network + ESO | **Mến** | Đông | — | 2.5d | **31/07 AM** |
| M9-08 | Param plan/runbook (`pending-reboot`) | **Mến** | Đức | M9-04 | 0.5d | **31/07 PM** |
| M9-02 | reviews cache + negative-cache + latch | **Đông** | Hải | — | 2d | **03/08 AM** |
| M9-05b | catalog `*sql.DB` generation reload | **Hải** | Mến | M9-01,M9-04 | 1d | **03/08 AM** |
| M9-07i | Schema code/scripts: dual-write + A/B + contract | **Đức** | Hải | M9-07d,M9-15a | 1.5d | **03/08** |
| M9-10 | MSK 4.0 prep + client/staging plan | **Mến** | Hải | M9-04 | 1d | **03/08** |
| M9-05a | accounting datasource generation + DBContext factory | **Đức** | Mến | M9-04,M9-07i | 1d | **04/08** |
| M9-05c | reviews pool generation reload | **Đông** | Mến | M9-02,M9-04 | 1.5d | **04/08** |
| M9-06 | Dormant-mode integration + staging-ready | **Hải** | Mến | 00,01,02,03,04,05a/b/c,07i,08,10 | 1d | **05/08** |
| M9-11 | ADR + runbook/evidence pack | **Mến** | Hải + mentor | 00,04,05a/b/c,07i,08,10,15a | 1.5d | **06/08 AM** |
| M9-12 | Staging rehearsal đầy đủ | **All (Đông điều phối)** | mentor | 06,07i,08,10,11 | 2d | **10/08 AM** |
| M9-15b | Production W1 approval | **Hải** | mentor/change approver | 11,12 | 0.25d | **10/08 PM** |
| M9-13 | **PROD W1** — 4 thao tác, schema pre-contract | **All (Hải IC)** | mentor | 11,12,15b | 0.5d | **11/08 AM** |
| M9-15c | Production W2 CONTRACT approval | **Hải** | mentor/change approver | 13 + revision B + bake ≥24h | 0.25d | **12/08 PM** |
| M9-14 | **PROD W2** — CONTRACT + evidence FINAL | **Đức (Hải IC)** | mentor | 13,15c + revision B 100% + bake ≥24h | 1d | **13/08** |
| M9-09 | RDS 17→18 Blue/Green — bonus | **Mến** | Hải | M9-14 + precheck §5.2 | 2d | post-final |
| M9-16 | IAM DB auth — hardening | **Mến** | Đức | M9-13 | 2d | post-demo |

**Capacity proof:** 29–31/07 bốn người chạy bốn nhánh độc lập. Đức dùng 30/07 PM cho 07d, nhận sign-off
31/07 AM rồi hoàn tất 07i ngày 03/08; Đông hoàn tất 02 và 05c tuần tự; Hải chỉ bắt đầu 05b sau khi cả
01+04 xong; Mến hoàn tất infra trước 08/10. M9-06 và M9-11 chạy song song ngày 05/08; M9-11 kết thúc
06/08 AM, rồi cả team rehearsal từ 06/08 PM đến 10/08 AM.

| Ngày | Hải | Đức | Đông | Mến |
|---|---|---|---|---|
| **29/07** | M9-01 | M9-03 | M9-00 | M9-04 |
| **30/07** | M9-01 | M9-03 AM → M9-07d PM | M9-00 AM → M9-02 PM | M9-04 |
| **31/07** | M9-01 AM → M9-05b PM | M9-15a AM → M9-07i | M9-02 | M9-04 AM → M9-08 PM |
| **03/08** | M9-05b AM, review/integration prep PM | M9-07i | M9-02 AM → M9-05c PM | M9-10 |
| **04/08** | review/buffer cho G1 | M9-05a | M9-05c | review + chuẩn bị M9-11 |
| **05/08** | M9-06 | support/review integration | evidence/integration support | M9-11 |
| **06 PM + 07 + 10 AM** | M9-12 + M9-15b | M9-12 | M9-12 điều phối | M9-11 AM 06/08 → M9-12 |
| **11/08** | M9-13 IC + deploy B | M9-13 schema | M9-13 evidence | M9-13 infra |
| **12/08** | bake monitor + M9-15c | bake/schema verify | route/evidence monitor | DB/infra monitor |
| **13/08** | M9-14 IC | M9-14 owner | load/evidence | DB/infra + evidence pack |

**Gate:** 🚩G1 (04/08) app/infra implementation xong · 🚩G2 (05–06/08) staging-ready + runbook ·
🚩G3 (10/08) rehearsal PASS + W1 approved · 🚩G4 (11/08) production W1 ·
🚩G5 (13/08) production W2 contract mentor-observed → **FINAL**.

> **Earliest-safe assumption:** mentor ký M9-15a sáng 31/07 và change approval phản hồi trong ngày.
> Nếu không, mọi task phụ thuộc tự động trượt; không bỏ staging, route gate hay bake ≥24h để giữ mốc 13/08.

---

# PHA A — Nền tảng (nhánh APP + OBS)

## M9-00 — Bộ đo "error = 0" + load harness
**Owner:** Đông · **Reviewer:** Hải · **Effort:** 1.5d · **Due: 30/07 AM**

**Description:** Xây bộ đo và load harness dùng chung để mở/đóng từng change window và kết luận
`PASS/FAIL` theo đúng góc nhìn khách hàng.

**Why:** Mandate yêu cầu tuyệt đối 0 request rớt dưới tải. Chỉ nhìn metric nội bộ hoặc tổng RPS có thể cho
false PASS khi route không có traffic, HTTP 200 chứa error body hoặc Prometheus trả empty series.

**How:**
1. Chốt danh sách route/store bị tác động, `N_route`, RPS floor và timeout budget end-to-end.
2. Cập nhật Locust để assert status, body semantics và gắn marker `window_id` cho từng thao tác.
3. Tạo Prometheus/Grafana query cho traffic, customer error, retry/stale, reconcile order, duplicate và MSK lag.
4. Viết preflight/postflight script fail-closed; đọc trạng thái flagd/fault nhưng không thay đổi nó.
5. Chạy baseline có lỗi giả lập để chứng minh dashboard/gate bắt được failure và empty series.

**Acceptance criteria**
- [ ] Dashboard 7 điều kiện (solution §2): traffic thật (delta>0, RPS>ngưỡng, **≥N request hoàn tất/cửa sổ** — chốt N trước, vd 500) · customer-fail windowed=0 · semantic assert (200+error-body=fail) · retry nội bộ được phép >0 (tách riêng) · reconcile `order_id` **kèm 0 duplicate** · MSK lag bounded→0 · fail-closed.
- [ ] Coverage matrix có **RPS floor + `N_route` + failure delta theo từng impacted path**: list/get/search;
      checkout→orderitem; reviews; checkout produce→accounting/fraud consume. Route bắt buộc thiếu traffic = FAIL,
      dù aggregate RPS xanh.
- [ ] Preflight: đọc trạng thái flagd/fault — **ACTIVE = NO-GO** (không mở cửa sổ); đã mở thì **mọi customer-fail = gate FAIL bất kể root cause**.
- [ ] Chốt ngân sách timeout end-to-end; nút bump `LOCUST_USERS` 10→30/trả về.

## M9-01 — catalog: stale-cache + readiness STARTUP-LATCH (Go)
**Owner:** Hải · **Reviewer:** Đông · **Effort:** 2.5d · **Due: 31/07 AM**

**Description:** Bổ sung canonical product snapshot, stale-serve, retry ngắn và readiness startup-latch cho
toàn bộ customer read path của `product-catalog`.

**Why:** RDS failover/reboot kéo dài hơn retry budget; nếu readiness phụ thuộc DB, pod bị rút khỏi endpoints
và cache không thể bảo vệ khách. Catalog phải tiếp tục phục vụ last-known-good trong outage.

**How:**
1. Re-verify list/get/search và health goroutine hiện tại; định nghĩa cache schema/revision.
2. Prime một snapshot đầy đủ từ DB trước khi latch `ever_primed=true`; list/get/search đều đọc từ snapshot.
3. Thêm background refresh; refresh fail giữ snapshot cũ, không xóa cache.
4. Tách readiness/liveness theo state machine solution §3.1 và thêm retry transient trong timeout budget.
5. Instrument metrics, unit test cache/search/latch và chaos test DB outage/cold-start.

**Acceptance criteria**
- [ ] Prime một **canonical snapshot của toàn bộ product**; list/get/search đều chạy từ snapshot in-memory
      (không prime/cache theo từng search query); refresh nền ~30s; refresh lỗi → giữ last-known-good.
- [ ] **Startup-latch** (solution §3.1): STARTUP chỉ Ready khi **prime đầy đủ** (kể cả khi DB reachable — chặn cold-start cache rỗng vào endpoints); STEADY: Ready = !shutdown && cache_schema_valid, DB chỉ là degraded-signal; LIVENESS không phụ thuộc DB/cache. Cache revision khớp app revision.
- [ ] Retry blip ngắn (4 lần, tổng chờ 700ms, trong timeout budget); `ConnMaxLifetime` 60s.
- [ ] Metrics: `cache_primed`, `ever_primed`, `cache_age_seconds`, `served_stale_total`, `db_retry_*`; max-staleness alert (vd 15′).
- [ ] Chaos 60–120s DB outage: pod **vẫn trong endpoints**, browse 200 stale, 0 customer-fail; pod mới cold-start giữa outage **không** vào endpoints (đúng latch).

## M9-02 — reviews: cache customer path + latch (Python)
**Owner:** Đông · **Reviewer:** Hải · **Phụ thuộc:** — · **Effort:** 2d · **Due: 03/08 AM**

**Description:** Đưa stale-cache và startup-latch vào các RPC customer-facing của `product-reviews`, đồng
thời loại bỏ dependency DB khỏi AI cache-key khi DB down.

**Why:** Hai RPC reviews hiện query DB trực tiếp và health `Check()` query DB thật; khi RDS down, pod vừa mất
data path vừa bị rút khỏi endpoints. Pool exhaustion cũng không được phép trở thành lỗi khách.

**How:**
1. Rebaseline `GetProductReviews`, `GetAverageProductReviewScore`, AI cache-key, `Check()` và pool lifecycle.
2. Prime list/average cho toàn bộ product ID, gồm negative-cache; lưu `review_version` last-known-good.
3. Chuyển customer path sang cache-first; DB chỉ dùng cho refresh, refresh/pool fail thì serve stale.
4. Thay DB-aware health bằng startup-latch per-replica; liveness chỉ theo process/shutdown.
5. Thêm metrics và test outage 60–120s, cold-start giữa outage, empty review và pool exhaustion.

**Acceptance criteria**
- [ ] Stale-cache **GetProductReviews + GetAverageProductReviewScore** cho **toàn bộ product ID, gồm NEGATIVE cache** (sản phẩm chưa có review).
- [ ] AI-assistant: cache key không phụ thuộc DB khi DB down (giữ `review_version` cuối trong memory; hết cách → fallback, không bypass).
- [ ] `Check()` bỏ query DB thật → đọc latch; giữ nhánh shutdown_event (graceful drain). Latch như M9-01, prime **per-replica**.
- [ ] **Pool exhaustion không chạm customer path** (v3.1): exhaustion chỉ làm refresh-attempt fail → serve stale; đo `pool_exhausted_total`, chứng minh không ánh xạ ra customer error. (Bỏ wording "fail 1 request".)
- [ ] Chaos 60–120s: pod trong endpoints, reviews 200 **có dữ liệu**, không leak conn.

## M9-03 — accounting idempotent + verify + bump producer
**Owner:** Đức · **Reviewer:** Hải · **Effort:** 1.5d · **Due: 30/07 AM**
*(mở đầu chuỗi accounting 03→07d→15a→07i→05a)*

**Description:** Làm consumer accounting idempotent theo `order_id`, xử lý replay an toàn và chuẩn bị
checkout producer chịu được MSK rolling.

**Why:** Offset được commit sau DB commit nên broker movement có thể replay message. Code hiện tại coi mọi
exception là transient, khiến duplicate key có thể kẹt partition hoặc làm sai dữ liệu.

**How:**
1. Xác định đúng unique constraint/primary key của order và đặt Kafka message key=`order_id`.
2. Phân loại 23505: chỉ constraint order replay mới đi vào nhánh compare; lỗi constraint khác vẫn fail.
3. Sau failed `SaveChanges`, dùng DbContext mới để đọc và canonical-compare order/items/shipping.
4. Payload khớp thì commit offset; khác thì ghi durable quarantine/DLQ, alert và dừng gate.
5. Pin producer retry/timeout rồi chaos test DB-commit thành công nhưng offset-commit thất bại.

**Acceptance criteria**

*Các tiêu chí dưới đây đã được siết từ v3.1:*
- [ ] Bắt unique-violation **23505** và **chỉ coi là replay hợp lệ khi `ConstraintName` = constraint của `order_id`** (không nuốt 23505 của constraint khác).
- [ ] Sau `SaveChanges` fail: **dùng DbContext MỚI/sạch** fetch lại và so sánh — không tiếp tục change tracker đang chứa entity `Added`.
- [ ] So khớp **cả aggregate**: order + orderitems + shipping (không chỉ parent).
- [ ] Cùng `order_id` nhưng payload **khác** → ghi **durable quarantine/DLQ** + dừng gate/alert — **không commit âm thầm, không retry vô hạn**.
- [ ] **Kafka message key = `order_id`** (verify; nếu chưa có thì set — cần cho ordering + dedupe).
- [ ] Chaos: giết offset-commit **sau** DB-commit → replay không duplicate, lag drain 0.
- [ ] checkout `Producer.Retry.Max` 3→10 + `Producer.Timeout` **con số cụ thể trong end-to-end deadline**.
- [ ] Verify failover ElastiCache (cart) + reboot-failover RDS staging (reconcile khớp).

> G1 chỉ đóng sau khi toàn bộ implementation 00–10 hoàn tất ngày 04/08; M9-03 riêng hoàn tất 30/07 AM.

---

# PHA B — Chuẩn bị (nhánh SEC + INFRA song song)

## M9-04 — Rotation infra (alternating-users) + Lambda network gate
**Owner:** Mến · **Reviewer:** Đông · **Effort:** 2.5d · **Due: 31/07 AM**

**Description:** Tạo hạ tầng Secrets Manager alternating-users cho ba app user tối thiểu quyền và đường
phân phối secret dạng file tới workload.

**Why:** Compliance #4 bắt buộc Secrets Manager rotation live. App hiện dùng master credential cố định;
alternating-users đổi cả username/password nên cần ba scope riêng và network/IAM đầy đủ cho rotation Lambda.

**How:**
1. Tạo `catalog_ro`, `reviews_ro`, `accounting_rw`; cấp đúng schema/table privilege và kiểm tra không dùng master.
2. Tạo ba app secret cùng admin secret reference; cấu hình rotation Lambda template PostgreSQL alternating.
3. Cấu hình SG Lambda→RDS:5432, NAT/Secrets Manager API, KMS và execution role tối thiểu quyền.
4. Cấu hình ESO→Kubernetes Secret→volume file; cấm `subPath`, đặt refresh interval và propagation SLO.
5. Render/plan/test network và Lambda trên staging fixture; production chỉ tạo config, chưa rotate/cutover.

**Acceptance criteria**
- [ ] Có đủ 3 user/3 secret/3 rotation scope; SQL grant test PASS và app user không có quyền master/DDL.
- [ ] Lambda nối được RDS, Secrets Manager và KMS; test network/IAM fail-closed.
- [ ] Rotation config hiểu đúng username clone; AWSCURRENT/AWSPREVIOUS policy được ghi trong runbook.
- [ ] ESO file mount không `subPath`; đo propagation nhỏ hơn overlap window.
- [ ] Không rotate hoặc cutover production trong M9-04; thao tác thật chỉ ở M9-12/M9-13.

## M9-05b — catalog generation reload (Go) · **Owner:** Hải · **Reviewer:** Mến ·
**Dep:** M9-01 + M9-04 · 1d · **Due: 03/08 AM**

**Description:** Cho `product-catalog` reload username/password live bằng cách thay thế `*sql.DB` theo
generation mà không đóng connection đang in-flight.

**Why:** Alternating-users đổi username nên không thể chỉ cập nhật password. Swap global trực tiếp có thể
đóng pool cũ khi request còn chạy và làm rớt customer request.

**How:**
1. Đọc secret file theo content hash/`..data` symlink và parse atomically.
2. Build `*sql.DB` generation mới, cấu hình pool và `PingContext` trước khi publish.
3. Atomic-swap current generation; request giữ handle generation đã borrow.
4. Đánh dấu generation cũ draining và chỉ `Close()` khi refcount=0 hoặc shutdown có kiểm soát.
5. Test password-change, username-change, invalid secret và rotate khi có concurrent browse traffic.

**Acceptance criteria**
- [ ] Reload được khi username hoặc password đổi; secret invalid không thay generation đang phục vụ.
- [ ] Request trả handle về đúng generation; không đóng connection in-flight.
- [ ] Test rotate dưới tải: pod UID giữ nguyên, catalog failure delta=0, connection mới dùng username mới.
- [ ] Có metrics/log cho generation, reload success/fail và drain duration; không log secret.

## M9-05c — reviews pool generation reload (Py) · **Owner:** Đông · **Reviewer:** Mến ·
**Dep:** M9-02 + M9-04 · 1.5d · **Due: 04/08**

**Description:** Bọc `ThreadedConnectionPool` của `product-reviews` bằng generation holder để hot-reload
toàn bộ DSN và drain pool cũ an toàn.

**Why:** Code hiện trả connection qua biến global trong `finally`; swap global có thể trả connection cũ vào
pool mới hoặc `closeall()` connection đang dùng, gây lỗi khách trong rotation.

**How:**
1. Thay API borrow bằng handle chứa `{generation,pool,conn}` và release về chính generation gốc.
2. Watch secret file bằng content hash/`..data`; build pool mới với username/password mới và query smoke-test.
3. Atomic-swap current generation; generation cũ chuyển draining, closeall chỉ khi refcount=0.
4. Bảo đảm refresh/cache path xử lý pool reload failure bằng serve stale.
5. Test concurrent RPC, exception trong `finally`, pool exhaustion, username-change và shutdown.

**Acceptance criteria**
- [ ] Không còn đường `putconn()` qua global pool cho connection đã borrow.
- [ ] Pool mới chỉ publish sau connect/query PASS; reload lỗi giữ pool/cache cũ.
- [ ] Rotate dưới tải: reviews failure delta=0, không leak/cross-return connection, pod UID không đổi.
- [ ] Metrics phân biệt pool generation, refcount, draining, reload error và exhaustion.

## M9-05a — accounting datasource generation (.NET) · **Owner:** Đức · **Reviewer:** Mến ·
**Dep:** M9-04 + M9-07i · 1d · **Due: 04/08**

**Description:** Thay `_dbContext` singleton bằng DBContext factory per-message và hot-swap toàn bộ
`NpgsqlDataSource` khi accounting credential đổi.

**Why:** `UsePeriodicPasswordProvider` không thay username; singleton DbContext không an toàn cho long-running
consumer và giữ datasource/connection cũ qua rotation.

**How:**
1. Tạo datasource generation holder từ secret file; validate datasource mới trước atomic swap.
2. Inject factory tạo DbContext/unit-of-work mới cho từng Kafka message từ current generation.
3. Giữ generation reference tới khi SaveChanges/compare hoàn tất; dispose generation cũ khi refcount=0.
4. Kết hợp logic idempotency M9-03 và dual-write M9-07i, không tạo hai đường persistence khác nhau.
5. Test rotate giữa DB commit/offset commit, username-change, datasource build fail và graceful shutdown.

**Acceptance criteria**
- [ ] Không còn `_dbContext` singleton; mỗi message dùng DbContext sạch và dispose đúng scope.
- [ ] Datasource reload được cả username/password; datasource lỗi không được publish.
- [ ] In-flight message hoàn tất trên generation gốc; replay vẫn idempotent và lag drain về 0.
- [ ] M9-12/M9-13 chứng minh accounting auth failure không chạm khách, pod UID không đổi và connection mới
      dùng đúng username.

## M9-07d — Schema design/ADR draft + mentor packet
**Owner:** Đức · **Reviewer:** Hải · **Phụ thuộc:** M9-03 · **Effort:** 0.5d · **Due: 30/07 PM**

**Description:** Thiết kế chiến lược schema evolution cho hai bảng thực tế (`products` và `orderitem`), xác định rõ
hai cửa sổ production W1/W2 và chuẩn bị gói ADR để mentor chốt trước khi viết migration production.

**Why:** Yêu cầu của mandate về bảng lớn và đường đọc của khách không cùng tồn tại trên một bảng trong hệ thống hiện tại.
Các bước contract như `SET NOT NULL`/`DROP COLUMN` là khó đảo ngược, nên cách ánh xạ hai bảng, semantics của watermark
và ranh giới W1/W2 phải được phê duyệt trước khi triển khai.

**How:**
1. Đo lại kích thước, lưu lượng, FK/index và mọi code reference của `products.categories` và
   `orderitem.created_at`.
2. Vẽ chuỗi expand → dual-write → backfill → validate → contract cho từng bảng, kèm revision A/B của ứng dụng.
3. Chốt semantics rollout watermark và cách `SET NOT NULL` tận dụng validated CHECK mà không giữ lock kéo dài.
4. Xác định rollback point cho W1, điều kiện không thể rollback sau W2 và các timeout/retry DDL bắt buộc.
5. Đóng gói diagram, SQL skeleton, risk register và evidence protocol để xin sign-off tại M9-15a.

**Acceptance criteria**
- [ ] Packet chốt cách 2 bảng, semantics watermark, hai production window và contract bảng lớn
      `orderitem.created_at SET NOT NULL` sau validated CHECK.
- [ ] Đủ diagram/SQL skeleton/risk để mentor ký M9-15a; chưa chạy DDL hay deploy production.

## M9-07i — Schema implementation: dual-write + A/B + SQL chi tiết
**Owner:** Đức · **Reviewer:** Hải · **Phụ thuộc:** M9-07d, M9-15a · **Effort:** 1.5d · **Due: 03/08**

**Description:** Hiện thực migration idempotent, dual-write/backfill cho `orderitem` và hai revision tương thích
ngược/thuận cho `products`, nhưng để thao tác contract production cho M9-14.

**Why:** Đây là phần triển khai trực tiếp compliance item #1. Nếu không có dual-write, bounded-lock DDL và hai revision
ứng dụng, backfill có thể không hội tụ hoặc revision cũ có thể lỗi trong lúc rolling deployment.

**How:**
1. Viết migration expand idempotent với `lock_timeout='1s'`, `statement_timeout='30s'` và retry có giới hạn.
2. Thêm dual-write `created_at=now()` sau rollout watermark, kèm query chứng minh mọi event/row mới đều được ghi.
3. Backfill theo lô; thêm constraint `NOT VALID`, chạy `VALIDATE CONSTRAINT`, rồi tạo index concurrently ngoài transaction.
4. Phát hiện và dọn invalid index trước khi retry; chuẩn bị `SET NOT NULL` và drop CHECK thành hai transaction riêng.
5. Tạo `products` revision A đọc `COALESCE` và revision B chỉ đọc cột mới; kiểm thử rolling A→B trên staging.
6. Chạy toàn chuỗi pre-contract dưới tải staging, quan sát `pg_locks` và lưu evidence cho M9-12/M9-14.

**Acceptance criteria**
- [ ] `orderitem` 8 bước: expand → **dual-write** → verify bằng row/event sau rollout watermark → backfill lô
      → NOT VALID → VALIDATE → INDEX CONCURRENTLY → **SET NOT NULL**.
- [ ] **`CREATE INDEX CONCURRENTLY` ngoài transaction block**; fail → detect + **DROP invalid index** trước khi retry.
- [ ] Contract đã chốt: `SET NOT NULL` tận dụng validated CHECK; commit xong mới drop CHECK bằng
      DDL/transaction riêng — không drop trong cùng command.
- [ ] Semantics watermark (đã chốt v3) ghi ADR; mọi DDL có `lock_timeout='1s'`+`statement_timeout='30s'`+retry.
- [ ] `products`: revision A (COALESCE) / B (chỉ cột mới); DROP ở **M9-14 trước mentor**.
- [ ] Diễn tập staging: `pg_locks` không giữ/chờ ACCESS EXCLUSIVE lâu.

## M9-08 — Param prep + verification
**Owner:** Mến · **Reviewer:** Đức · **Dep:** M9-04 · 0.5d · **Due: 31/07 PM**

**Description:** Chuẩn bị Terraform plan và runbook bật `pg_stat_statements` qua static parameter, bao gồm reboot-failover,
kiểm tra runtime và phương án hoàn nguyên; task này chưa apply production.

**Why:** Compliance item #3 yêu cầu thay đổi static parameter không downtime. Trạng thái `pending-reboot` trong plan không
chứng minh parameter đã có hiệu lực, nên cần kiểm tra cả AWS control plane và PostgreSQL sau reboot.

**How:**
1. Đọc giá trị `shared_preload_libraries` hiện tại và tạo thay đổi dạng append, không ghi đè thư viện đang có.
2. Sinh và review Terraform plan với `apply_method="pending-reboot"`; lưu plan artifact có định danh.
3. Viết bước CLI kiểm tra `DBParameterGroups[].ParameterApplyStatus` trước và sau reboot-failover.
4. Viết bốn kiểm tra runtime: `SHOW` → `CREATE EXTENSION IF NOT EXISTS` → query `pg_extension` →
   `SELECT ... FROM pg_stat_statements LIMIT 1`.
5. Ghi ngưỡng go/no-go, metric theo dõi và rollback bỏ parameter rồi reboot-failover lần nữa.

**Acceptance criteria**
- [ ] Terraform **append** (không overwrite) `shared_preload_libraries`; parameter `apply_method="pending-reboot"`
      thấy trong plan. M9-08 chỉ chuẩn bị plan/runbook, **không apply production trước rehearsal**.
- [ ] Sau apply ở M9-12 (staging) và M9-13 (production): CLI `describe-db-instances` xác nhận
      `DBParameterGroups[].ParameterApplyStatus=pending-reboot`; plan hoặc `ApplyMethod` của parameter không đủ.
- [ ] Runbook reboot-failover + 4 check sau reboot (`SHOW` → `CREATE EXTENSION IF NOT EXISTS` → `pg_extension` → `SELECT ... LIMIT 1`); rollback = bỏ param + reboot lại.

## M9-10 — MSK 4.0 prep + client gate + staging cluster plan
**Owner:** Mến · **Reviewer:** Hải · **Dep:** M9-04 · 1d · **Due: 03/08**

**Description:** Chuẩn bị nâng MSK 3.9→4.0, xác minh tương thích của cả ba Kafka client và thiết kế staging cluster thật
để rehearsal trước thao tác production một chiều.

**Why:** Đây là compliance item #2 và MSK không hỗ trợ downgrade tại chỗ. Sai protocol, bootstrap list hoặc offset handling
có thể làm ngừng consumer/producer hay replay đơn hàng, nên client gate phải hoàn tất trước go/no-go production.

**How:**
1. Gọi `get-compatible-kafka-versions` đúng region/cluster và khóa target 4.0.x được AWS trả về.
2. Lập inventory version/config của ba client; xác nhận multi-broker bootstrap, `V3_0_0_0` có chủ đích và các timeout/retry.
3. Định nghĩa test produce/consume/rebalance cho cả ba client trên broker 4.0, gồm leader movement và ngắt offset commit.
4. Thiết kế staging MSK cùng topology production cần thiết để test hành vi cluster-scoped, không thay bằng topic tách.
5. Viết rolling runbook với metric lag/ISR, checkpoint go/no-go và phương án phục hồi bằng cluster thay thế.
6. Ước tính thời gian/chi phí, quy định teardown staging ngay sau khi M9-12 PASS.

**Acceptance criteria**
- [ ] `get-compatible-kafka-versions` xác nhận 4.0.x; runbook rolling; kỳ vọng under-replicated 30–60′.
- [ ] **Client gate checklist:** test **cả 3 client** với broker 4.0 (chạy thật ở M9-12 trên staging cluster); bootstrap string đủ nhiều broker; `ProtocolVersion=V3_0_0_0` xác nhận **có chủ đích** (ghi ADR); chaos leader-movement + offset-commit interruption.
- [ ] **Go/no-go checklist** (MSK **không downgrade** — phục hồi = cluster thay thế kiểu Mandate #8, không gọi là rollback).
- [ ] Staging MSK cluster plan: KRaft/m7g.large×3/RF=3/isr=2/SCRAM, ~$18–25/ngày, provisioning ~40′, **xoá ngay sau M9-12**.

## M9-06 — Integration dormant-mode + staging-ready (KHÔNG cutover production)
**Owner:** Hải · **Reviewer:** Mến · **Dep:** 00,01,02,03,04,05a/b/c,07i,08,10 ·
1d · **Due: 05/08**

**Description:** Tích hợp các nhánh ứng dụng, rotation, schema, observability và infrastructure thành một release candidate
có mặc định dormant/pre-cutover, sẵn sàng triển khai staging nhưng chưa làm thay đổi production.

**Why:** Các thay đổi được phát triển song song có thể xung đột tại manifest, secret mount, pool lifecycle hoặc feature gate.
Một mốc integration riêng giúp phát hiện lỗi giao nhau trước rehearsal và ngăn cutover ngoài cửa sổ được duyệt.

**How:**
1. Rebase/merge các nhánh theo dependency, xử lý xung đột và khóa commit/image digest của release candidate.
2. Chạy build, unit/integration test và `helm template`; xác nhận mọi cutover/rotation flag mặc định dormant.
3. Dùng test secret để kiểm tra generation swap, drain in-flight và hai đường rollback mà không chạm production.
4. Tạo staging values hoàn chỉnh và production values ở trạng thái reviewed-only, không apply.
5. Chạy smoke test tích hợp cho catalog, reviews, accounting và evidence harness; chuyển artifact cho M9-11/M9-12.

**Acceptance criteria**
- [ ] Build/test artifact và manifest chung; secret/cutover feature gate mặc định **pre-cutover/dormant**.
- [ ] Unit/integration test generation swap, drain và hai rollback path bằng fixture/test secret; không rotate
      secret, đổi credential mode, apply static param hay chạy DDL trên production.
- [ ] Staging values/runbook sẵn sàng cho M9-12; production values chỉ là reviewed plan, chưa apply.
- [ ] Hai rollback đã implement: rotation→**AWSPREVIOUS**; cutover→**pre-cutover credential mode**. Secret cũ
      và đường master chỉ được thu hồi sau production bake + rotation PASS ở M9-13/M9-14.

## M9-11 — ADR + runbook · **Owner:** Mến · **Reviewer:** Hải + mentor ·
**Dep:** 00,04,05a/b/c,07i,08,10,15a · 1.5d · **Due: 06/08 AM**

**Description:** Hợp nhất quyết định kiến trúc, lệnh vận hành, evidence query, vai trò và rollback/go-no-go thành bộ ADR +
runbook có thể thực thi lặp lại cho rehearsal, W1 và W2.

**Why:** Zero-downtime production operation cần trình tự xác định và bằng chứng đo được, không thể dựa vào kiến thức ngầm.
Mentor/change approver cũng cần một artifact duy nhất để đánh giá rủi ro và dừng thao tác đúng checkpoint.

**How:**
1. Chuẩn hóa các ADR: rotation, MSK, cache/latch, watermark, schema contract và mô hình W1/W2.
2. Viết từng bước preflight, command, expected output, start/end marker và evidence query cho bốn thao tác.
3. Gắn bảy evidence gate và route matrix vào các checkpoint go/no-go; quy định ai đọc metric và ai ra quyết định.
4. Lập rollback matrix phân biệt AWSPREVIOUS, pre-cutover mode, parameter revert, schema pre-contract và MSK replacement.
5. Thêm timeline, communication/escalation, artifact version và checklist bàn giao ca.
6. Walkthrough với Hải và mentor; sửa mọi điểm mơ hồ trước khi khóa bản dùng cho M9-12.

**Acceptance criteria**
- [ ] ADR: rotation alternating (vs IAM) · MSK-as-#2 (vs BG) · cache+startup-latch · watermark · contract
      `SET NOT NULL` · mô hình production W1/W2.
- [ ] Runbook 4 thao tác: lệnh, kỳ vọng, 7 điều kiện + route matrix, rollback đúng bản chất (MSK go/no-go;
      BG restore/PITR; rotation 2 loại), start/end marker và evidence query cho từng cửa sổ.

---

# PHA C — Tổng duyệt

## M9-12 — Staging rehearsal (RDS clone + MSK staging thật)
**Owner:** All (**Đông điều phối**) · **Reviewer:** mentor (mời dự) ·
**Dep:** 06,07i,08,10,11 · 2d · **Due: 10/08 AM**

**Description:** Rehearsal end-to-end trên RDS clone và MSK staging thật, dưới tải đại diện, theo đúng thứ tự và artifact
sẽ dùng ở production; Đông điều phối evidence timeline.

**Why:** Rotation, reboot-failover và MSK upgrade chứa bước một chiều hoặc có kết nối bị drop. Rehearsal là nơi duy nhất
an toàn để chứng minh runbook, ứng dụng và recovery phối hợp đúng trước khi xin production approval.

**How:**
1. Provision topology staging, deploy đúng release candidate và xác nhận baseline traffic/evidence gate đều xanh.
2. Chạy schema pre-contract, client gate 4.0, app-user cutover, rotation ba scope, static parameter reboot và MSK rolling
   theo đúng runbook.
3. Inject failover 60–120s, leader movement, offset-commit interruption và secret username change; thực thi rollback
   cho từng phase còn reversible.
4. Ghi thời lượng, metric, route failure delta, pod UID, credential generation, reconcile order và Kafka lag ở mỗi marker.
5. Tổ chức retrospective, sửa/run lại bước chưa đạt và chỉ đánh dấu PASS khi toàn bộ gate cùng đạt.
6. Đính kèm chi phí rồi teardown staging resources ngay sau PASS và xác minh không còn tài nguyên tính phí.

**Acceptance criteria**
- [ ] Staging đủ topology; **chạy client gate 4.0** (M9-10) tại đây trước khi rolling.
- [ ] Cutover app-user + rotate **cả 3 secret/scope** trên staging; chứng minh username-change, generation
      drain và hai rollback path trước khi mở production window.
- [ ] Trọn 4 thao tác dưới tải; 7 điều kiện + **route-level traffic matrix** xanh; rollback chỉ phase reversible
      (schema pre-contract, AWSPREVIOUS, pre-cutover mode, param revert) — không có "rollback MSK".
- [ ] Bấm giờ; chốt runbook; **xoá staging ngay sau** (ghi chi phí).
- [ ] **Prod demo vẫn là gate chính thức** — staging chỉ được tính nghiệm thu nếu mentor xác nhận văn bản.

## M9-15a — Mentor design sign-off + gia hạn · **Owner:** Đức · **Reviewer:** mentor ·
**Dep:** M9-07d · **Effort:** 0.25d · **Due: 31/07 AM**

**Description:** Xin mentor xác nhận bằng văn bản về cách ánh xạ hai bảng, contract bảng lớn, mô hình hai cửa sổ W1/W2
và gia hạn cho mandate đã quá hạn.

**Why:** Compliance item #1 đang conditional theo cách diễn giải topology thực tế; đồng thời deadline 19/07 đã qua.
Không có quyết định và gia hạn được lưu vết thì team không đủ thẩm quyền khóa runbook hay mở rehearsal/production.

**How:**
1. Gửi packet M9-07d trước buổi review, nêu rõ quyết định cần mentor chọn và hệ quả của từng phương án.
2. Walkthrough schema sequence, watermark, large-table contract, W1/W2 và evidence protocol.
3. Ghi nguyên văn quyết định, ngày duyệt, người duyệt và điều kiện kèm theo trong ADR/change record.
4. Cập nhật solution/WBS/runbook nếu mentor chọn phương án khác hoặc yêu cầu thêm evidence.
5. Đặt hard gate: thiếu sign-off/gia hạn thì M9-11, M9-12, M9-13 và M9-14 không được bắt đầu.

**Acceptance criteria**
- [ ] Dựa trên M9-07d, xác nhận bằng văn bản: cách 2 bảng; contract bảng lớn `SET NOT NULL`; production gồm
      W1 pre-contract và W2 contract sau bake; mentor xem trực tiếp M9-14 hoặc duyệt evidence protocol.
- [ ] Ghi ngày mentor duyệt gia hạn quá hạn 19/07. Thiếu M9-15a → không khoá M9-11, không mở rehearsal/prod.

## M9-15b — Production W1 approval · **Owner:** Hải · **Reviewer:** mentor/change approver ·
**Dep:** M9-11,M9-12 · **Effort:** 0.25d · **Due: 10/08 PM**

**Description:** Mở và được phê duyệt change ticket riêng cho production W1, khóa chính xác artifact, cửa sổ, vai trò,
go/no-go và bốn thao tác pre-contract sẽ thực hiện.

**Why:** W1 chứa rotation, reboot-failover và MSK upgrade không thể tùy ý lặp hoặc downgrade. Approval sau rehearsal
đảm bảo người có thẩm quyền chấp nhận rủi ro và team chỉ chạy phiên bản đã được kiểm chứng.

**How:**
1. Đính kèm rehearsal PASS, runbook đã khóa, evidence summary, risk/rollback matrix và chi phí vào ticket.
2. Ghi rõ commit/image digest, Terraform plan, target resource IDs, thứ tự thao tác và route-level traffic floor.
3. Chỉ định Hải là incident commander, người thực thi từng bước, mentor observer và kênh escalation.
4. Xác nhận flagd preflight, MSK go/no-go, thời gian cửa sổ và tiêu chí abort tại từng checkpoint.
5. Lưu approval ID/timestamp; sau approval không đổi artifact, nếu đổi phải rehearsal/re-approve phần ảnh hưởng.

**Acceptance criteria**
- [ ] Change ticket riêng cho M9-13: rehearsal PASS, runbook, go/no-go, 4 thao tác, route matrix, khung giờ mentor.
- [ ] Ticket có approval ID/timestamp, artifact version và danh sách owner/observer; thiếu một mục thì W1 là NO-GO.

## M9-15c — Production W2 CONTRACT approval · **Owner:** Hải · **Reviewer:** mentor/change approver ·
**Dep:** M9-13 + revision B + bake ≥24h · **Effort:** 0.25d · **Due: 12/08 PM**

**Description:** Xin approval riêng cho production W2 chỉ sau khi revision B chạy 100%, bake đủ 24 giờ và có bằng chứng
không còn code/query tham chiếu cột cũ.

**Why:** `SET NOT NULL` và `DROP COLUMN` là contract/destructive changes có rollback rất hạn chế. Tách W2 khỏi W1
ngăn team contract sớm chỉ để giữ lịch và buộc kiểm tra tương thích sau bake.

**How:**
1. Xác minh rollout revision B=100%, không có pod/job/consumer cũ và bake clock đủ tròn 24 giờ.
2. Quét source, migration, dashboard/query và database activity để chứng minh không còn reference cột cũ.
3. Đính kèm W1 PASS, lock rehearsal, traffic floor, exact SQL, timeout/retry và evidence query vào ticket W2.
4. Ghi rõ thứ tự `SET NOT NULL` → commit → drop CHECK riêng → `products DROP COLUMN`, cùng stop condition.
5. Lấy approval ID/timestamp ngay trước cửa sổ; bất kỳ thiếu hụt nào tự động dời W2, không rút ngắn bake.

**Acceptance criteria**
- [ ] Change ticket riêng cho M9-14: W1 PASS, revision B=100%, bake ≥24h và evidence không còn reference
      cột cũ; scope gồm `orderitem SET NOT NULL` rồi drop CHECK riêng + `products DROP COLUMN`.
- [ ] Thiếu M9-15b → không mở W1; thiếu M9-15c → không mở destructive W2.
- [ ] Mốc 13/08 là **earliest**: chưa đủ tròn 24h bake hoặc approval/evidence chưa xong → tự động NO-GO và
      dời W2; tuyệt đối không rút ngắn bake để giữ lịch.

> 🚩 **G3 (10/08):** rehearsal PASS + M9-15a/b đầy đủ.

---

# PHA D — Demo & sau demo

## M9-13 — PROD W1: 4 thao tác, schema pre-contract · **Owner:** All (**Hải IC**) ·
**Reviewer:** mentor · **Dep:** 11,12,15b · **Effort:** 0.5d · **Due: 11/08 AM**

**Description:** Thực thi production window W1 dưới tải thật và mentor quan sát: schema pre-contract, credential
cutover/rotation ba scope, static parameter reboot-failover và MSK rolling upgrade; sau đó deploy revision B.

**Why:** W1 là bằng chứng production chính cho compliance items #2–#5 và phần reversible/pre-contract của #1.
Chạy theo một cửa sổ có marker và gate chung cho phép quy failure đúng thao tác, dừng sớm và chứng minh error delta bằng 0.

**How:**
1. Xác nhận M9-15b, artifact hashes, owner/observer, flagd inactive và bảy evidence gate trước start marker.
2. Mở tải tối thiểu theo từng impacted route; chạy schema expand→dual-write→backfill→validate→index và dừng trước contract.
3. Rolling cutover app-user rồi rotate từng secret/scope; tại mỗi scope kiểm tra username, generation drain và pod UID.
4. Apply static parameter, xác nhận pending-reboot, reboot-failover và chạy đủ bốn kiểm tra runtime.
5. Re-check MSK go/no-go rồi rolling upgrade; theo dõi ISR, client errors, offset/reconcile và lag drain về ngưỡng.
6. Chốt end marker/evidence, deploy revision B 100%, khởi động bake clock và giữ đường pre-cutover/secret cũ.

**Acceptance criteria**
- [ ] Preflight flagd ACTIVE=NO-GO; 7 điều kiện + traffic floor/`N_route` **theo từng impacted path** xanh
      xuyên suốt; không đụng flagd/Directive #1.
- [ ] Thứ tự: schema expand→dual-write→backfill→validate→index (chưa contract) → rolling cutover app-user +
      rotate cả 3 scope → static param + reboot-failover → MSK rolling.
- [ ] Chứng minh latch, generation reload username-changed cả ba, order reconcile/0 duplicate và MSK lag drain.
- [ ] Sau W1 deploy revision B 100%; bắt đầu bake clock và giữ pre-cutover credential mode/secret cũ.

## M9-14 — PROD W2: CONTRACT dưới tải (mentor xem) + evidence
**Owner:** Đức (**Hải IC**) · **Reviewer:** mentor ·
**Dep:** 13,15c + revision B 100% + bake ≥24h · 1d · **Due: 13/08**

**Description:** Thực thi production window W2 cho hai schema contract dưới tải và trước mentor, sau đó hoàn tất evidence
pack chung W1+W2 để nghiệm thu mandate.

**Why:** Mandate yêu cầu chuỗi expand→migrate→contract hoàn chỉnh trên production mà không downtime. Chỉ W2 mới chứng minh
`SET NOT NULL` trên bảng lớn và xóa cột cũ an toàn sau revision B/bake.

**How:**
1. Kiểm tra M9-15c, bake ≥24h, revision B=100%, không còn reference cũ và route-level traffic floor trước marker.
2. Chạy `ALTER COLUMN created_at SET NOT NULL` với bounded lock; commit và kiểm tra dữ liệu/traffic.
3. Drop validated CHECK bằng transaction riêng, với cùng lock/statement timeout và retry policy.
4. Chạy `products DROP COLUMN categories`; theo dõi route matrix và query/database errors xuyên suốt.
5. Reconcile order, Kafka lag, customer-fail delta, DDL duration/locks và mọi evidence gate sau end marker.
6. Đóng evidence pack, mentor sign-off, xác nhận staging đã teardown và ghi lại follow-up hardening/bonus.

**Acceptance criteria**
- [ ] Re-verify không còn app/reference cột cũ; route-level traffic floor đạt trước khi mở W2.
- [ ] Bảng lớn: `ALTER COLUMN created_at SET NOT NULL` tận dụng validated CHECK; commit; sau đó drop CHECK
      bằng DDL/transaction riêng. `products`: `DROP COLUMN categories`. Mọi DDL có lock timeout + retry.
- [ ] Cả hai contract chạy **DƯỚI TẢI trước mentor**; failure delta từng route=0 và hoàn tất chuỗi
      expand→dual-write→backfill→validate→contract đúng wording đề.
- [ ] Evidence pack đủ W1+W2 + reconcile + ADR/runbook; staging đã xoá; MSK 4.0 lag ổn.

## M9-09 — RDS 17→18 Blue/Green — bonus · **Owner:** Mến · **Reviewer:** Hải ·
**Dep:** M9-14 + precheck solution §5.2 · **Effort:** 2d · **Due:** post-final

**Description:** Thử nghiệm/nâng RDS PostgreSQL 17→18 bằng Blue/Green deployment như một hạng mục bonus sau khi mandate
đã nghiệm thu; không dùng task này thay thế MSK compliance item #2.

**Why:** Blue/Green có thể giảm rủi ro cho major-version upgrade tương lai, nhưng có limitations riêng về DDL replication,
managed master password, connection drop và rollback. Tách post-final tránh làm tăng critical path của mandate.

**How:**
1. Chỉ bắt đầu sau M9-14 và change approval/budget riêng; chạy toàn bộ precheck tại solution §5.2 đúng region.
2. Xác minh target 18.4 còn khả dụng, extension/parameter compatibility và IAM policy có đủ cả blue/green resources.
3. Đóng băng DDL sau khi tạo Blue/Green; tạo deployment và kiểm tra schema/data/replication lag phía green.
4. Chạy smoke/load test trên green, chuẩn bị ứng dụng chịu connection drop và xác nhận switchover criteria.
5. Switchover dưới tải, quan sát customer-fail delta, reconnect, query health và version runtime.
6. Giữ/cleanup blue theo policy; nếu thất bại dùng restore/PITR hoặc kế hoạch phục hồi đã duyệt, không tuyên bố lossless rollback.

**Acceptance criteria**
- [ ] Chỉ chạy sau M9-14 với approval và budget riêng; bỏ qua task không ảnh hưởng trạng thái PASS của mandate.
- [ ] Precheck solution §5.2 PASS và CLI đúng region xác nhận target version ngay trước khi khóa runbook.
- [ ] Green vượt qua schema/data/extension/load checks; không có DDL ngoài kế hoạch sau thời điểm tạo Blue/Green.
- [ ] Switchover dưới tải có route-level customer-fail delta=0, reconnect ổn định và runtime báo đúng version.
- [ ] Evidence ghi rõ connection drop/rollback limitation và kết quả cleanup hoặc retention của blue.

## M9-16 — IAM DB auth — hardening · **Owner:** Mến · **Reviewer:** Đức ·
**Dep:** M9-13 · **Effort:** 2d · **Due:** post-demo

**Description:** Đánh giá và triển khai tùy chọn IAM database authentication sau demo như hardening, có feature gate
và rollback; không thay thế Secrets Manager alternating-users rotation của compliance item #4.

**Why:** IAM auth có thể giảm credential sống lâu và tăng khả năng audit, nhưng token ngắn hạn làm thay đổi pool lifecycle,
policy và capacity. Tách riêng giúp mandate chứng minh đúng cơ chế rotation trước khi thêm độ phức tạp.

**How:**
1. Đánh giá RDS capacity/connection rate, driver support và chi phí vận hành token provider cho ba service.
2. Bật IAM DB auth qua IaC trong môi trường staging; tạo DB user và IAM policy/resource theo least privilege.
3. Hiện thực token refresh trước expiry, pool generation/reconnect và metrics cho token/auth failure.
4. Test staging với token expiry, failover, pool drain và rolling deployment dưới tải.
5. Rollout production từng service qua feature gate; giữ Secrets Manager path làm rollback trong bake window.
6. Chỉ cân nhắc bỏ credential path cũ sau ADR/change approval riêng và bằng chứng production ổn định.

**Acceptance criteria**
- [ ] Tài liệu ghi rõ M9-16 là post-demo hardening và không được tính thay compliance item #4.
- [ ] IAM/DB policy least-privilege, resource/region/account đúng và không cấp quyền master ngoài nhu cầu.
- [ ] Test token refresh/expiry, failover và pool reconnect dưới tải không làm pod restart hay tăng customer-fail delta.
- [ ] Feature gate rollback về Secrets Manager được rehearsal và production rollout có bake/evidence riêng.
- [ ] Không thu hồi alternating-users rotation hoặc secret cũ nếu chưa có ADR và change approval độc lập.

---

## Ràng buộc & nhắc nhở (mọi task)
- **KHÔNG** đụng flagd/`/flagservice`/filter fault — preflight chỉ đọc; **ACTIVE = NO-GO**.
- Terraform `plan -out`→`apply tfplan`; GitOps/ArgoCD base `main`; `helm template`; secret file-mount không `subPath`.
- **Giờ vận hành, RPS/`N_route` tối thiểu theo từng impacted path** — không dùng maintenance window.
- Thao tác một chiều: rehearsal staging trước; production W1/W2 có M9-15b/c riêng; mỗi irreversible action
  chỉ chạy một lần trong đúng cửa sổ đã duyệt.

## Quy tắc phối hợp team 4 người
- Mỗi PR có owner và reviewer khác người; Hải là integration/incident commander nhưng không tự review task mình.
- Đức giữ độc quyền chuỗi accounting/schema 03→07d→07i→05a; không giao người khác sửa cùng
  `Consumer`/`DBContext`/entity trong cửa sổ này.
- Đông giữ product-reviews trong 02→05c; Hải giữ product-catalog trong 01→05b; hai nhánh chỉ hội tụ ở M9-06.
- Mến sở hữu rotation/infra/param/MSK và runbook; mọi secret/production permission vẫn cần reviewer/gate.
- Ngày trong bảng là **earliest-safe**, không phải deadline buộc phải đạt. Gate ngoài team trễ → dời downstream.
