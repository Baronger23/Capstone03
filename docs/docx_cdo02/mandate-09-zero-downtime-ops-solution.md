# Mandate #9 — Solution: Vận hành managed zero-downtime dưới tải (0 request rớt)

**Đội:** CDO02 (Reliability + Cost Optimization)
**Ngày soạn:** 28/07/2026 · **v2:** 28/07 (vòng 1) · **v3:** 29/07 (vòng 2) · **v3.1:** 29/07 (vòng 3) ·
**v3.2:** 29/07 (vòng 4)
**Nền:** Mandate #8 hoàn tất (3 store managed, mentor PASS).

> ### 🔧 Changelog v3.2 (vòng 4 — đóng execution-order, contract & evidence gate)
> 1. **Không còn production cutover trước rehearsal:** M9-06 chỉ tạo artifact/integration ở dormant mode và
>    chứng minh *staging-ready*; M9-12 mới cutover/rotate trên staging; M9-13 mới cutover/rotate production.
> 2. Production là **hai cửa sổ có approval riêng**: W1=M9-13 (4 thao tác, schema pre-contract) và
>    W2=M9-14 (CONTRACT sau bake); mỗi thao tác một chiều chỉ chạy một lần trên production.
> 3. **Contract bảng lớn đã chốt:** `accounting.orderitem.created_at SET NOT NULL` sau validated CHECK;
>    M9-14 contract cả `orderitem` và `products` dưới tải.
> 4. Evidence gate dùng **coverage theo từng impacted route/store** với `N_route`; tổng RPS không được che
>    route không được exercise.
> 5. Catalog prime **canonical product snapshot**, rồi list/get/search chạy in-memory.
> 6. Rotation gồm **3 app secret/scope** (`catalog_ro`, `reviews_ro`, `accounting_rw`); phải chứng minh
>    username-change cho cả ba.
>
> ### 🔧 Changelog v3.1 (vòng 3 — chỉnh state machine & gate, KHÔNG đổi kiến trúc)
> 1. **Readiness đổi sang STARTUP-LATCH** (hết mâu thuẫn "OR DB reachable" vs "prewarm trước Ready"): pod chỉ
>    Ready khi **prime ĐẦY ĐỦ dataset bắt buộc**; sau `ever_primed` thì DB reachable chỉ còn là degraded-signal. **§3.1.**
> 2. **flagd/fault đang ACTIVE lúc preflight = NO-GO**; lỗi khách trong cửa sổ = **FAIL bất kể root cause** —
>    không có chuyện "loại nhiễu khỏi kết quả". **§2.**
> 3. **Pool-exhaustion không được chạm customer path** (cache-first) — bỏ wording "fail 1 request". **§3.3.**
> 4. **Hai loại rollback credential tách bạch**: rotation→AWSPREVIOUS · cutover→pre-cutover mode (giữ suốt bake
>    window; chưa thu hồi master ngay). **§7.2.**
> 5. Siết acceptance: idempotency (ConstraintName, fresh-context compare, quarantine/DLQ, key=order_id) ·
>    schema SQL (index ngoài txn, dọn invalid index, verify theo watermark, chốt CHECK vs SET NOT NULL) ·
>    MSK client gate (test 3 client với 4.0, pin con số) · param `apply_method`. **§4.2, §5.1, §6.**
> 6. **#1 là CONDITIONAL** tới khi mentor chốt: (a) cách 2 bảng; (b) contract sau bake — mentor xem trực tiếp
>    ở cửa sổ follow-up (M9-14) hoặc phê duyệt văn bản. **§4, §9.**
>
> ### 🔧 Changelog v3 (blocker vòng 2) — đọc trước
> 1. **Readiness là lỗ hổng chết người của stale-cache (v2 sót):** cả `product-catalog` (health goroutine
>    ping DB) lẫn `product-reviews` (`Check()` chạy **query DB thật** mỗi probe, dòng 940) đều trả
>    `NOT_SERVING` khi DB down → **K8s rút pod khỏi endpoints → cache có đúng cũng không nhận traffic**.
>    v3 định nghĩa lại **readiness contract**: SERVING khi *cache primed* HOẶC DB reachable. **§3.1.**
> 2. **Cache của product-reviews KHÔNG nằm trên customer path** (chỉ ở AI-assistant, và cache key cần
>    `get_review_version()` từ DB): `GetProductReviews`/`GetAverageProductReviewScore` gọi DB trực tiếp.
>    → Phải **thêm** stale-cache cho list/average, không phải "verify cái sẵn có". **§3.1, §3.3.**
> 3. **Alternating-users đổi cả USERNAME lẫn password** → `UsePeriodicPasswordProvider` không đủ; phải
>    **rebuild toàn bộ pool/datasource** + drain kiểu **generation** (con trỏ pool cũ chỉ đóng khi refcount=0).
>    accounting còn phải bỏ `DBContext` singleton. **§7.2.**
> 4. **Schema orderitem: khôi phục bước DUAL-WRITE** (v2 làm rơi mất — thiếu nó backfill không bao giờ hội
>    tụ dưới live traffic) + định nghĩa semantics giá trị backfill. **§4.2.**
> 5. **accounting chưa idempotent** → MSK rolling có thể replay message sau khi DB đã commit → duplicate key
>    → code hiện coi mọi exception là transient → **kẹt partition vĩnh viễn**. Phải sửa trước khi rolling. **§5.1.**
> 6. **MSK KHÔNG downgrade được** → bỏ khái niệm "rollback" cho MSK upgrade; thay bằng go/no-go trước khi
>    bắt đầu + phương án cluster thay thế. Rehearsal cần **staging MSK cluster thật** (upgrade là
>    cluster-scoped, "topic tách" vô nghĩa). **§5.1, §9.**
> 7. Rotation Lambda cần **network gate** (RDS:5432 + đường ra Secrets Manager API + KMS); secret mount
>    **cấm `subPath`**; watch symlink/nội dung chứ không tin mtime; rollback = **AWSPREVIOUS**. **§7.2.**
> 8. P1: bỏ chữ "no-lock" (→ *bounded-lock*); min completed-request mỗi cửa sổ; preflight ghi trạng thái
>    flagd/fault; BG bonus dời **hẳn post-demo**; param verification đầy đủ; freshness contract cho cache.
>
> ⚠️ Codebase đang đổi hằng ngày — mọi tham chiếu đo 28–29/07, **re-verify ngay trước khi implement**.

---

## 0. Directive → giải pháp (bản đồ nhanh)

Thước đo: **0 request khách bị rớt** trong toàn bộ cửa sổ thay đổi, **dưới tải thật**, **trong giờ vận hành**.

| # | Yêu cầu | Store | Kỹ thuật (v3) | Mục |
|---|---|---|---|---|
| 5 | App nuốt blip kết nối | cả 3 | **Nền tảng, làm TRƯỚC**: stale-cache trên **toàn bộ read path** + **readiness startup-latch** + retry blip ngắn | §3 |
| 1 | Online schema migration | RDS | expand → **dual-write** → backfill → validate → contract (2 lần deploy A/B); *bounded-lock* (lock_timeout + retry DDL) | §4 |
| 2 | Nâng version lớn | **MSK 3.9→4.0 rolling (primary)**; điều kiện tiên quyết: **accounting idempotent** | §5 |
| 3 | Đổi param cần reboot | RDS | `pg_stat_statements` → reboot-with-failover; read sống nhờ cache+readiness mới | §6 |
| 4 | Xoay credential live (Secrets Manager) | RDS | **alternating-users rotation** + app **rebuild pool theo generation** (username+password đều đổi) | §7 |

RDS Blue/Green 17→18: **bonus hẳn post-demo** (§5.2). ElastiCache 9.0→9.1 chỉ minor — không dùng cho #2.

---

## 1. Điểm xuất phát (verify 28–29/07)

**Stores:** RDS `techx-tf3-postgres` 17.9 Multi-AZ (param group custom) · ElastiCache `techx-tf3-valkey` 9.0
2-node Multi-AZ · MSK `techx-tf3-kafka` 3.9.x.kraft 3 broker RF=3/isr=2. Nâng được: RDS→18.3/18.4 (verify lại
đúng region trước khi khoá runbook), MSK→4.0.x/4.1.x.

**Posture app — các khoảng trống #9 phải đóng:**

| Service | Hiện trạng (đo 29/07) | Khoảng trống |
|---|---|---|
| `product-catalog` (Go) | query 1 phát, không cache/retry; **health goroutine → NOT_SERVING khi ping DB fail** (`main.go` ~297) | stale-cache + **đổi readiness contract** |
| `product-reviews` (Py) | `GetProductReviews`/`GetAverageProductReviewScore` → **DB trực tiếp** (server 904/908→969/988); cache guardrails chỉ ở AI-path, cache key cần `get_review_version()` **từ DB**; **`Check()` chạy query DB thật** (940) | stale-cache cho list/average + cache-key không phụ thuộc DB + **đổi readiness** |
| `cart` (.NET) | StackExchange reconnect tốt | verify failover |
| `checkout` (Go/sarama) | acks=all, idempotent producer, Retry.Max=3 | bump Retry.Max cho MSK rolling |
| `accounting` (.NET) | consumer manual-commit (không mất đơn) **nhưng**: `_dbContext` **singleton** (Consumer.cs:53); catch-all exception → seek/retry **vô hạn** → duplicate key khi replay = **kẹt partition** | **idempotent theo order_id** + DBContext per-message + phân loại lỗi |

---

## 2. Thước đo "0 request rớt" — điều kiện chứng minh

Trong **mỗi** cửa sổ thao tác, phải chứng minh **đồng thời**:

1. **Có traffic thật**: `request_total` delta > 0, **RPS liên tục > ngưỡng**, và **số request hoàn tất tối
   thiểu mỗi cửa sổ** (đặt trước, vd ≥500/cửa sổ) — chống "0 lỗi vì 0 request".
2. **Customer-visible failure = 0** (windowed delta, không cumulative): Locust failures không tăng; Envoy
   non-2xx route khách = 0.
3. **Locust semantic assertions**: HTTP 200 nhưng body `{"error": ...}` **tính là fail** (product-reviews
   `fetch_product_reviews` trả error trong body).
4. **Internal transient error/retry ĐƯỢC PHÉP > 0** — chính là bằng chứng nuốt blip
   (`db_retry_attempt_total`, `db_retry_recovered_total`, `served_stale_total`). KHÔNG đặt "internal error = 0".
5. **Zero-loss reconcile theo `order_id`**: checkout success → Kafka event → DB order khớp theo id, kèm
   **0 duplicate** (quan trọng khi MSK rolling — §5.1).
6. **MSK lag bounded trong cửa sổ và drain về 0 sau đó** (không bắt =0 từng giây).
7. **Fail-closed**: Prometheus query rỗng series = FAIL, không coi là 0.

**Coverage bắt buộc theo route/store (không được chỉ nhìn tổng RPS):**

| Cửa sổ | Đường phải có tải và bằng chứng riêng |
|---|---|
| Schema `products` | list/get/search: mỗi route có RPS > 0, ≥`N_route` request hoàn tất và failure delta = 0 |
| Schema `orderitem` | checkout success > 0; row/event sau rollout watermark > 0; `created_at IS NULL` sau watermark = 0 |
| Rotation + RDS reboot | catalog + reviews có tải; checkout→Kafka→accounting reconcile; auth/query failure của cả 3 app user không chạm customer path |
| MSK rolling | checkout produce > 0; accounting và fraud consume > 0; reconcile/duplicate/lag đạt điều kiện 5–6 |

`N_route` và RPS tối thiểu của **từng** route được chốt ở M9-00 trước rehearsal. Route bắt buộc không đạt
traffic floor = **FAIL**, dù tổng traffic toàn hệ thống xanh.

**Preflight mỗi cửa sổ:** đọc **trạng thái flagd/fault-injection** (KHÔNG đụng, không tắt): nếu có fault đang
**ACTIVE** → **NO-GO, chưa mở cửa sổ thay đổi**. Một khi cửa sổ đã mở, **mọi customer request fail đều làm gate
FAIL bất kể root cause** (DB, MSK hay fault được bơm) — không có khái niệm "loại trừ nhiễu khỏi kết quả". Xác
định **ngân sách timeout end-to-end** (client→CloudFront→Envoy→frontend→gRPC→DB) — retry policy phải nằm trong đó.

---

## 3. NỀN TẢNG — App chịu blip (Yêu cầu #5) — v3 thiết kế lại

> **Nhận thức đúng (sau 2 vòng review):** failover RDS kéo **60–120s**. Retry không che nổi. Stale-cache che
> được **nhưng chỉ khi pod còn nhận traffic** — mà readiness hiện tại (REL-02: DB-aware) sẽ **rút pod khỏi
> endpoints khi DB down**. Vậy #5 = **cache + readiness contract + retry**, thiếu một trong ba là sụp.

### 3.1 Stale-serve cache trên TOÀN BỘ customer read path + readiness contract

**Phủ cache (last-known-good, in-memory):**
- `product-catalog`: prime **một canonical snapshot chứa toàn bộ product**; list/get/search đều đọc/tính từ
  snapshot này (không cache theo từng search query). Refresh nền ~30s; refresh lỗi → **giữ nguyên**
  last-known-good (không bao giờ xoá cache vì lỗi).
- `product-reviews`: **GetProductReviews + GetAverageProductReviewScore** (hiện gọi DB trực tiếp — phải thêm
  mới, không phải verify). AI-assistant: **cache key không được phụ thuộc DB** khi DB down — giữ
  `review_version` cuối cùng theo product trong memory; hết cách thì đi thẳng fallback, không bypass cache
  chỉ vì thiếu key.

**Readiness contract v3.1 — STARTUP-LATCH** (sửa mâu thuẫn của v3: `primed OR DB reachable` cho phép pod
cold-start có DB nhưng cache rỗng vào endpoints — DB fail trước khi prime xong là rớt request):
```
STARTUP  : Ready CHỈ KHI required cache dataset đã prime ĐẦY ĐỦ
           (ever_primed=false → NOT_SERVING, KỂ CẢ khi DB reachable)
STEADY   : sau khi ever_primed=true → Ready = !shutdown_event && cache_schema_valid
           (DB reachable chỉ còn là DEGRADED-HEALTH signal/metric — KHÔNG quyết định readiness)
LIVENESS : chỉ process/gRPC alive — không phụ thuộc DB lẫn cache freshness
```
- **"Primed đầy đủ" định nghĩa cụ thể:** catalog = canonical snapshot có **toàn bộ product ID** và list/get/
  search đều phục vụ được từ snapshot; reviews =
  list + average cho **toàn bộ product ID, gồm cả NEGATIVE cache** cho sản phẩm chưa có review. **Mỗi replica
  prime riêng**; cache schema/revision phải **khớp app revision** (mismatch = chưa primed).
- `product-reviews` `Check()` bỏ query DB thật mỗi probe → đọc trạng thái latch; giữ nhánh shutdown_event
  NOT_SERVING (graceful drain).
- Ghi chú ADR: đây là **tiến hoá của REL-02** — "khả năng phục vụ" = latch đã prime, không đồng nhất với
  "DB reachable". Không phải gỡ REL-02.

**Freshness contract (tránh tuyên bố tuyệt đối "stale bao lâu cũng được"):**
- `cache_primed` (gauge 0/1), `cache_age_seconds`, `served_stale_total`, revision/schema của cache.
- **Max staleness chấp nhận**: đặt trước (vd 15 phút = nhiều lần ngân sách failover); vượt → alert (không tự
  ngắt phục vụ, nhưng vận hành phải biết).
- Chaos test **phải xác nhận pod còn trong `kubectl get endpoints` suốt 60–120s DB outage** và khách 200.

### 3.2 Retry — chỉ cho blip ngắn
4 lần thử, backoff 100/200/400ms (**tổng chờ 700ms**), chỉ lỗi tạm thời (`driver.ErrBadConn`, `net.Error`,
PG `57P01/57P03`); nằm trong ngân sách timeout end-to-end (§2). `product-catalog` hạ `ConnMaxLifetime` 5′→60s.
Chaos test giữ **đúng 60–120s** (không phải vài trăm ms).

### 3.3 product-reviews — thực trạng code (rebaseline 29/07)
`database.py`: `db_pool` global + `init_db_pool()` + `get_db_connection()` (discard conn `closed`; pool hỏng
thật → `closeall()`+rebuild; **không rebuild** khi `PoolError` exhausted — tránh leak REL-05). **Không còn
`_run_query`.**
⚠️ **Wording v3.1 về exhaustion:** trong thiết kế cache-first, "fail 1 request" là KHÔNG chấp nhận được nếu đó
là request khách. Exhaustion chỉ được phép làm **refresh attempt fail → customer path tiếp tục serve stale**;
đo `pool_exhausted_total` và chứng minh nó **không ánh xạ ra bất kỳ customer error nào**. Hàm fetch trả conn qua **biến global** trong `finally` → hot-swap pool kiểu "đổi global rồi
`closeall()`" sẽ trả conn cũ vào pool mới / đóng conn đang in-flight → **phải dùng generation holder (§7.2)**.

### 3.4 (Tuỳ chọn) RDS Proxy
Giảm nhiễu failover nhưng **không hấp thụ hết** (AWS: BG switchover vẫn drop connection, app phải reconnect).
Bổ trợ, không thay cache+readiness. +$22/tháng.

---

## 4. YÊU CẦU #1 — Online schema migration (tâm điểm)

Nguyên tắc: mọi thời điểm schema tương thích với app đang chạy; **`DROP` chỉ khi không còn app nào reference**.
Wording đúng về khoá: `ADD/DROP COLUMN` **vẫn lấy `ACCESS EXCLUSIVE`** nhưng giữ rất ngắn nếu lấy được ngay →
mục tiêu là **bounded-lock / không giữ-chờ khoá kéo dài**, kèm:
```sql
SET lock_timeout = '1s'; SET statement_timeout = '30s';  -- retry DDL nếu lock_timeout, không xếp hàng chặn traffic
```

### 4.1 `catalog.products` — categories CSV → text[] (2 lần deploy A/B)
```
1. EXPAND      ADD COLUMN categories_arr text[] (nullable)
2. Deploy A    đọc COALESCE(categories_arr, string_to_array(categories,','))  (cả 2 cột còn)
3. BACKFILL    UPDATE ... WHERE categories_arr IS NULL   (10 dòng, tức thời)
4. VERIFY      browse xanh; số danh mục khớp
5. Deploy B    đọc CHỈ categories_arr — không còn reference `categories`
6. GATE        100% pod revision B + bake ≥1 ngày
7. CONTRACT    DROP COLUMN categories   (điểm không quay lui — sau demo, M9-14)
```

### 4.2 `accounting.orderitem` (395k, live writes) — v3 KHÔI PHỤC DUAL-WRITE
```
1. EXPAND       ADD COLUMN created_at timestamptz (nullable)                [bounded-lock]
2. DUAL-WRITE   deploy accounting ghi created_at = now() cho row MỚI
                (gated env ORDERITEM_WRITE_CREATED_AT)                      ← v2 làm rơi bước này
3. VERIFY       row mới không còn NULL (đo trước khi backfill)
4. BACKFILL     UPDATE ... IS NULL theo lô 5–10k (có nghỉ; theo dõi ReplicaLag/autovacuum)
                → backfill HỘI TỤ được vì nguồn NULL mới đã bị chặn ở bước 2
5. CHECK        ADD CONSTRAINT ... CHECK (created_at IS NOT NULL) NOT VALID
6. VALIDATE     VALIDATE CONSTRAINT (SHARE UPDATE EXCLUSIVE — không chặn đọc/ghi)
7. INDEX        CREATE INDEX CONCURRENTLY (created_at)
8. CONTRACT     ALTER COLUMN created_at SET NOT NULL
                → commit thành công, rồi DROP CHECK tạm bằng một DDL/transaction RIÊNG
```
**Chi tiết SQL bắt buộc (v3.1):** `CREATE INDEX CONCURRENTLY` chạy **ngoài transaction block**; nếu fail →
**phát hiện & DROP index invalid trước khi retry**. Verify dual-write bằng **row/event phát sinh SAU rollout
watermark** (mốc revision accounting mới nhận traffic), không dùng câu mơ hồ "row mới hết NULL". Chốt trong
ADR quyết định rõ: validated CHECK là enforcement tạm; M9-14 chạy `ALTER TABLE accounting.orderitem ALTER
COLUMN created_at SET NOT NULL` dưới tải, tận dụng CHECK đã validate để bỏ full-table scan. **Không drop CHECK
trong cùng command**: commit `SET NOT NULL` thành công trước, rồi mới drop CHECK bằng DDL/transaction riêng;
cả hai có `lock_timeout` + retry.

**Semantics giá trị backfill (bắt buộc ghi ADR):** row lịch sử **không có** thời điểm tạo thật. Chính sách
chọn: backfill bằng **migration watermark cố định** (timestamp bắt đầu backfill) và ghi rõ *"giá trị ≤
watermark nghĩa là 'tạo trước migration, thời điểm chính xác không xác định'"* — hoặc đặt tên cột trung thực
hơn (`ingested_at`). Chốt design ở M9-07d và mentor ký M9-15a; **không** gọi sentinel là "thời điểm tạo thật".

> Hệ thống không có bảng vừa-lớn-vừa-đọc-khách → tách 2 bảng như trên; **xin mentor xác nhận** cách này (hoặc
> chuyển 1 bảng chạy trọn chu kỳ theo yêu cầu mentor). **Compliance #1 vì thế là CONDITIONAL cho tới khi có
> 2 sign-off: (a) cách 2 bảng; (b) contract chạy sau bake — mentor quan sát trực tiếp ở cửa sổ follow-up
> (M9-14, Reviewer=mentor, chạy dưới tải) hoặc phê duyệt văn bản trước rồi review evidence sau.**

---

## 5. YÊU CẦU #2 — Nâng version lớn

### 5.1 PRIMARY — MSK 3.9 → 4.0 rolling (điều kiện tiên quyết: accounting idempotent)

**⚠️ Điều kiện tiên quyết (blocker v3):** accounting hiện *DB commit → rồi mới commit offset*. Broker roll có
thể làm **offset commit fail SAU khi DB đã ghi** → message replay → `INSERT` trùng `order_id` → duplicate-key
exception → code hiện coi **mọi** exception là transient → seek/retry **vô hạn = kẹt partition**. Trước khi
rolling, accounting phải:
- **Idempotent theo `order_id`**: bắt `PostgresException` unique-violation (23505) → nếu order đã tồn tại và
  dữ liệu **khớp** → coi là success, **commit offset**; nếu **khác** → alert data-integrity, đưa ra xử lý
  riêng (không retry mù).
- Chaos test: giết offset-commit sau DB-commit → replay **không tạo duplicate**, lag drain về 0.

**Thao tác:** bump checkout `Producer.Retry.Max` 3→10 + chốt `Producer.Timeout` **bằng con số cụ thể nằm trong
end-to-end deadline** (không ghi chung chung "tăng timeout"); `update-cluster-kafka-version` → AWS reboot
**từng broker** (~10–20′/broker, under-replicated tạm thời — bình thường); RF=3/isr=2 → produce/consume liên tục.

**Client gate (trước khi bấm nút — v3.1):** test **cả 3 client** (checkout/sarama · accounting/Confluent ·
fraud/Kotlin) với **broker 4.0 trên staging** trước upgrade; verify bootstrap string chứa **đủ nhiều broker**;
xác nhận `ProtocolVersion = V3_0_0_0` (sarama) là lựa chọn tương thích **có chủ đích** với 4.0 (ghi ADR);
chaos: **leader movement** + **offset-commit interruption** (đi cùng idempotency ở trên).

**Sự thật về "rollback" (v3):** **MSK KHÔNG hỗ trợ downgrade version.** Vậy: (a) **go/no-go TRƯỚC khi bắt
đầu** (preflight checklist + staging rehearsal); (b) sau khi bắt đầu: monitor, không có "hạ 4.0 về 3.9";
(c) phương án phục hồi nếu upgrade hỏng = **cluster thay thế** (dựng 3.9/4.0 mới + producer-first cutover như
Mandate #8) — ghi trong runbook, không gọi là rollback.

**Rehearsal:** upgrade là **cluster-scoped** → "topic tách" trên prod cluster là vô nghĩa. Cần **staging MSK
cluster thật** cùng cấu hình (KRaft, m7g.large ×3 — floor của KRaft, RF=3/isr=2, SASL/SCRAM): chi phí
~**$18–25/ngày**, provisioning ~30–45′, **xoá ngay sau rehearsal** (§8).

### 5.2 BONUS (dời hẳn POST-DEMO) — RDS 17→18 Blue/Green
Chỉ sau M9-14 (schema đã contract xong, prod ổn định) và khi thoả **tất cả** precheck: BG **không replicate
DDL** (DDL sau khi tạo BG → green *Replication degraded* → xoá tạo lại); **managed master password là
limitation của BG** — precheck/xử lý; switchover **drop connection** (read sống nhờ §3); **blue read-only sau
switchover ⇒ rollback = restore/PITR, không lossless**; IAM (nếu dùng) policy cả blue+green; verify target
18.4 đúng region.

---

## 6. YÊU CẦU #3 — Param cần reboot, zero-downtime

Thêm `pg_stat_statements` vào `shared_preload_libraries` (static) của `techx-tf3-postgres17` → **reboot-with-
failover** (Multi-AZ, ~60–120s ngắt kết nối). Read path sống nhờ **cache + readiness contract (§3.1)** —
KHÔNG phải retry; write (`accounting`) replay không mất đơn.

**Verification đầy đủ (v3):**
- Terraform **append, không overwrite** giá trị `shared_preload_libraries` hiện có; parameter khai báo
  `apply_method = "pending-reboot"` (đây là thứ thấy được trong plan).
- Sau apply: **CLI xác nhận** instance/param group thực sự ở trạng thái `pending-reboot` (plan chỉ cho thấy
  `apply_method` — trạng thái thật phải hỏi RDS).
- Sau reboot-failover, trên DB:
  ```sql
  SHOW shared_preload_libraries;                                    -- có pg_stat_statements
  CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
  SELECT 1 FROM pg_extension WHERE extname='pg_stat_statements';
  SELECT * FROM pg_stat_statements LIMIT 1;                         -- query được thật
  ```
- Chỉ tuyên bố hoàn tất sau đủ các check trên. Rollback: bỏ param → reboot-failover lần nữa.

---

## 7. YÊU CẦU #4 — Secrets Manager rotation (đúng chữ của đề)

### 7.1 Vấn đề gốc (giữ nguyên)
App nối RDS bằng **user MASTER** qua env cố định lúc pod start; RDS tự xoay master (7 ngày) → sẽ gãy. Vá bằng
app-user riêng + rotation + hot-reload.

### 7.2 Thiết kế v3 — alternating-users nghĩa là USERNAME CŨNG ĐỔI

**Hạ tầng (M9-04):**
- Ba app user tối thiểu quyền và **ba app secret/rotation scope riêng**: `catalog_ro`/`reviews_ro` (SELECT),
  `accounting_rw`; bỏ master khỏi app. Không dùng một secret quyền hợp nhất cho cả ba service.
- Secrets Manager **alternating-users rotation** (template PostgreSQL của AWS): rotation tạo/luân phiên
  `user` ↔ `user_clone` → **secret đổi CẢ username LẪN password**; cred cũ còn valid trong overlap → 0 auth-fail.
- **Network gate cho rotation Lambda (bắt buộc, AWS yêu cầu):** Lambda trong VPC nối được **RDS:5432** (SG
  allow từ SG Lambda); có đường ra **Secrets Manager API** (NAT sẵn có — lưu ý VPC hiện KHÔNG có endpoint
  secretsmanager; nếu thêm endpoint là thêm phí, mặc định đi NAT); quyền **KMS** decrypt/encrypt secret;
  execution role đủ (SecretsManagerRotationPolicy).
- ESO ghi secret ra **volume file**. **CẤM `subPath`** (K8s không cập nhật secret mount qua subPath). Ghi rõ
  **propagation SLO**: ESO `refreshInterval` + kubelet sync ≈ phút — phải < cửa sổ overlap của alternating.

**App hot-reload (M9-05) — rebuild pool theo GENERATION (vì username đổi):**
- **Watch đúng cách:** theo dõi **thư mục/symlink** của secret mount (K8s swap `..data` symlink) hoặc poll
  **nội dung/hash** — không tin mtime của inode cũ.
- **Generation holder** (mẫu chung 3 ngôn ngữ):
  ```
  generation = { pool/datasource, refcount, draining }
  borrow  → tăng refcount, TRẢ VỀ ĐÚNG generation đã mượn (không qua biến global)
  release → giảm refcount của generation gốc
  rotate  → build generation MỚI từ secret (username+password mới) → swap atomic con trỏ "current"
            → generation cũ draining; CHỈ close khi refcount = 0 (không closeall khi còn in-flight)
  ```
- `accounting` (.NET): **rebuild toàn bộ `NpgsqlDataSource`** khi username/password đổi
  (`UsePeriodicPasswordProvider` **không đủ** — nó không đổi username). Bỏ `_dbContext` **singleton**
  (Consumer.cs:53) → **DBContext factory per-message/unit-of-work** đọc datasource hiện hành.
- `product-catalog` (Go): build `*sql.DB` mới → swap con trỏ → drain rồi `Close()` DB cũ.
- `product-reviews` (Py): generation holder bọc `ThreadedConnectionPool` — vì các `finally` hiện trả conn qua
  **global `db_pool`**, phải trả theo generation đã mượn; pool cũ `closeall()` chỉ khi refcount=0.

**Demo #4 trước mentor:** chạy `aws secretsmanager rotate-secret` theo từng app secret → chứng minh AWSCURRENT
**version đổi**, `pg_stat_activity` thấy connection mới dùng **username mới**, **pod UID không đổi**, customer
errors = 0. **Cả ba scope** phải có evidence username-changed (không chỉ password); có thể chạy tuần tự trong
cùng cửa sổ để giữ traffic/evidence rõ ràng.

**Hai loại rollback tách bạch (v3.1):**
(a) *rollback ROTATION* = khôi phục **AWSPREVIOUS** (lệnh cụ thể trong runbook) + app tự reload;
(b) *rollback CUTOVER* = quay về **pre-cutover credential mode** bằng feature gate — vì vậy trong **bake window
sau cutover**: giữ mode cũ sẵn sàng, **chưa xoá secret cũ**, và **chỉ thu hồi đường master sau khi app-user đã
bake + rotation test PASS**. Không mô tả mơ hồ "lật cờ".

### 7.3 IAM DB auth = hardening post-demo (không phải compliance #4).

---

## 8. Ngân sách (v3)

| Hạng mục | Chi phí | Ghi chú |
|---|---|---|
| Cache/readiness/retry/idempotency/schema/rotation code | ~$0 | app-side |
| Secrets Manager rotation | ~$1–2/tháng | secret fee + Lambda (đi NAT, không cần endpoint mới) |
| MSK rolling (primary #2) | $0 trên prod | |
| **Staging MSK cluster cho rehearsal** | **~$18–25/ngày** | m7g.large×3 (floor KRaft); provisioning ~40′; **xoá ngay sau** |
| Staging RDS clone (rehearsal) | ~vài USD | restore từ snapshot, xoá sau |
| RDS Blue/Green (bonus, post-demo) | vài USD một lần | 2 bộ DB vài giờ |
| RDS Proxy (tuỳ chọn) | +$22/tháng | chỉ nếu quyết định riêng; bù bằng dọn VPC endpoint |

Vẫn giữ nguyên tắc: không đảo ngược quyết định reliability nào của #8; tổng phát sinh ≤ vài chục USD một lần.

---

## 9. Trình tự thực thi

- **Chuẩn bị trước rehearsal không được cutover production:** M9-06 chỉ build/test artifact, manifest và
  feature gate ở dormant mode; không rotate secret, đổi credential mode hay apply static param lên production.
- **Rehearsal đầy đủ trên STAGING** (RDS clone từ snapshot + **staging MSK cluster thật** + app trỏ staging):
  chạy trọn 4 thao tác dưới tải, bấm giờ, chốt runbook. **Thử rollback CHỈ cho các phase còn reversible**
  (schema pre-contract, rotation AWSPREVIOUS, param revert). **MSK: go/no-go trước, không có downgrade.**
- **Production có HAI cửa sổ được phê duyệt riêng**; mỗi thao tác một chiều chỉ chạy một lần:
  - **W1 / M9-13:** #1 schema (expand→dual-write→backfill→validate→index, chưa contract) → #4 cutover app-user
    + rotate cả 3 scope → #3 apply static param + reboot-failover → #2 MSK rolling.
  - **W2 / M9-14:** sau revision B=100% và bake ≥1 ngày, contract `orderitem.created_at SET NOT NULL` rồi
    `DROP products.categories`, dưới tải và mentor quan sát. Mốc lịch là earliest; chưa đủ tròn 24h bake hoặc
    chưa có approval W2 thì NO-GO và dời cửa sổ, không rút ngắn bake.
  Prod là **gate chính thức** (staging chỉ được tính nghiệm thu nếu mentor xác nhận rõ bằng văn bản).
- Preflight mỗi cửa sổ: 7 điều kiện §2 + ghi trạng thái flagd/fault + change-approval của mentor cho prod.

---

## 10. Ràng buộc bất biến
- **KHÔNG** đụng flagd/`/flagservice`/filter fault — preflight chỉ **ghi nhận** trạng thái flag.
- Directive #1 giữ nguyên; secret qua Secrets Manager→ESO (file mount, không subPath), không hardcode.
- Terraform `plan -out`→`apply` (không auto-approve); GitOps/ArgoCD base `main`; `helm template` verify.
- **Giờ vận hành, RPS tối thiểu cố định** — không né bằng maintenance window.

---

## 11. Hành động chạm workload & vì sao khách vẫn 0 rớt (v3)

| Hành động | Cửa sổ tác động | Cơ chế đỡ khách |
|---|---|---|
| Rollout app (cache/readiness, A/B, rotation, idempotency) | rolling `maxUnavailable:0` | 0 rớt (chứng minh ở Mandate #3) |
| DDL expand/validate/index (`lock_timeout` + retry) | ACCESS EXCLUSIVE **rất ngắn**, không xếp hàng | bounded-lock; accounting ghi tiếp |
| Dual-write + backfill lô | WAL/ReplicaLag tăng nhẹ | lô nhỏ có nghỉ; theo dõi lag/autovacuum |
| **reboot-with-failover (#3)** | **60–120s** ngắt kết nối | **cache primed + readiness mới giữ pod trong endpoints**; write replay |
| **rotate-secret (#4)** | ~giây; username+password đổi | overlap alternating; generation swap, không đóng conn in-flight |
| **MSK rolling (#2)** | under-replicated 30–60′ | RF=3/isr=2; producer retry; **consumer idempotent (đã sửa)** |
| Contract (M9-14) | `orderitem SET NOT NULL` + `products DROP`; không quay lui | validated CHECK; 100% revision B + bake; bounded DDL |
| BG switchover (bonus, post-demo) | drop connection <1′ | cache; **rollback = restore/PITR (blue read-only)** |

---

## 12. Checklist việc phải làm
- [ ] §2 bộ đo 7 điều kiện + **traffic floor/N theo từng impacted route** + preflight flagd-state + timeout budget.
- [ ] §3 canonical product snapshot phục vụ list/get/search + list/average reviews (gồm **negative-cache**) + AI-key không phụ
      thuộc DB + **readiness STARTUP-LATCH** (prime đầy đủ trước Ready; steady không phụ thuộc DB) + liveness
      không DB + freshness metrics; chaos 60–120s giữ pod trong endpoints.
- [ ] §4 script schema (dual-write; semantics backfill; contract bảng lớn `SET NOT NULL` rồi drop CHECK
      riêng; `products DROP` sau bake; lock_timeout+retry).
- [ ] §5 accounting **idempotent 23505** + chaos replay; bump producer retry; staging MSK cluster; runbook
      go/no-go (không "rollback").
- [ ] §6 param verification 4 bước sau reboot.
- [ ] §7 rotation alternating (**3 app secret/scope**; Lambda network gate; file mount không subPath;
      generation holder 3 service; DBContext factory; test username-changed cả ba; rollback AWSPREVIOUS).
- [ ] §9 staging rehearsal → production W1 + W2 có approval riêng; ADR + runbook (M9-11).
- [ ] **Mentor/change sign-off:** M9-15a=gỡ CONDITIONAL của #1 + gia hạn; M9-15b=approval production W1;
      M9-15c=approval destructive CONTRACT W2/M9-14.

---

*Ký: CDO02. Phối hợp: CDO01 (rotation/IAM/SG), AIO02 (product-reviews AI-path cache).
Tham chiếu code đo 28–29/07/2026 — re-verify trước khi implement.*
