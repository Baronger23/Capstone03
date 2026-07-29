# Mandate #9 — Solution: Vận hành managed zero-downtime dưới tải (0 request rớt)

**Đội:** CDO02 (Reliability + Cost Optimization)
**Ngày soạn:** 28/07/2026 · **Hạn directive gốc:** 19/07/2026
**Trạng thái hạ tầng làm cơ sở:** đã hoàn tất Mandate #8 (3 store lên managed, mentor PASS) — xem
[`mandate-08-nghiem-thu.md`](../mandate-08-nghiem-thu.md).

> **Vì sao TF3 làm được #9:** Directive #9 dành cho đội **đã ở tầng managed**. TF3 vừa hoàn tất #8 (đưa
> Postgres→RDS, Valkey→ElastiCache, Kafka→MSK), nên giờ có đủ hạ tầng managed **thật, đang phục vụ khách**
> để thực hiện đúng bài #9: thay đổi hạ tầng dữ liệu **dưới tải** mà **không rớt một request nào**.

---

## 0. Directive đòi gì → giải pháp (bản đồ nhanh)

Thước đo của #9 **khắt khe hơn SLO ≥99%**: yêu cầu **0 request khách bị rớt** (error count = 0) trong
**toàn bộ** cửa sổ thay đổi, **dưới tải thật** (load-generator chạy liên tục), làm **trong giờ vận hành**
(không được "cắt bảo trì lúc vắng khách").

| # | Yêu cầu directive | Store áp dụng | Kỹ thuật chọn (tối ưu) | Mục |
|---|---|---|---|---|
| 5 | App nuốt được blip kết nối (retry/pool/proxy) | cả 3 | **Nền tảng bắt buộc, làm TRƯỚC** — retry ở product-catalog/product-reviews, verify cart/checkout | §3 |
| 1 | Online schema migration (expand→backfill→dual-read/write→contract), không lock | RDS | `catalog.products` (đường đọc của khách) + `accounting.orderitem` (bảng lớn 395k, no-lock at scale) | §4 |
| 2 | Nâng **version lớn** zero-downtime | RDS **17→18** (Blue/Green) — hoặc MSK **3.9→4.0** (rolling) | §5 |
| 3 | Đổi param **cần reboot** zero-downtime | RDS | thêm `pg_stat_statements` vào `shared_preload_libraries` → **reboot-with-failover** (Multi-AZ) | §6 |
| 4 | Xoay credential **live**, không restart gây rớt | RDS | **RDS IAM database authentication** (bỏ hẳn mật khẩu tĩnh) — vá luôn 1 lỗ hổng thật | §7 |

> ⚠️ **Hai phát hiện quan trọng khi rà code hiện tại** (chi tiết §2):
> 1. **App đang nối RDS bằng chính user MASTER**, mật khẩu do RDS tự xoay (mặc định 7 ngày) và app đọc qua
>    **biến môi trường cố định lúc pod khởi động** → lần RDS tự xoay mật khẩu tiếp theo sẽ **làm gãy app**.
>    Đây là **rủi ro production có thật**, không chỉ là bài tập #4.
> 2. **`product-catalog` (Go) và `product-reviews` (Python) không có retry** khi kết nối DB chớp tắt →
>    bất kỳ failover/switchover nào cũng **rớt request khách**. Phải vá trước (§3) thì #1–#4 mới đạt "0 rớt".

---

## 1. Điểm xuất phát — hạ tầng & app hiện tại

**Managed stores (đã verify live 28/07, account `197826770971`):**

| Store | Định danh | Cấu hình | Ai dùng |
|---|---|---|---|
| RDS PostgreSQL | `techx-tf3-postgres` | **17.9**, db.t4g.micro, **Multi-AZ**, param group **custom** `techx-tf3-postgres17`, backup 7d/PITR | `accounting` (ghi), `product-catalog` + `product-reviews` (đọc) |
| ElastiCache Valkey | `techx-tf3-valkey` | 9.0.0, 2 node Multi-AZ, TLS+AUTH, param group **default** `default.valkey9` | `cart` |
| MSK Kafka | `techx-tf3-kafka` | 3.9.x.kraft, 3 broker/3 AZ, RF=3, isr=2, SASL/SCRAM | `checkout` (producer), `accounting`+`fraud-detection` (consumer) |

**Đường đi của khách (nơi "0 request rớt" được chấm):**
`CloudFront → ALB → frontend-proxy (Envoy) → frontend → {product-catalog, product-reviews, cart, checkout}`.
`load-generator` (Locust) bơm tải liên tục — đây vừa là "tải thật" mà directive yêu cầu, vừa là **thước đo
khách** (Locust tự đếm request fail).

**Tùy chọn nâng cấp có thật (đã tra API, không phỏng đoán):**

| Store | Version hiện tại | Nâng lên được | Ghi chú |
|---|---|---|---|
| RDS | 17.9 | **major 18.3 / 18.4**, minor 17.10 | major 17→18 = bài "nâng version lớn" chuẩn nhất |
| MSK | 3.9.x.kraft | **4.0.x.kraft**, 4.1.x.kraft | Kafka 3→4 là major thật, MSK nâng **rolling** từng broker |
| ElastiCache | 9.0.0 | 9.1 (chỉ **minor**) | Valkey chưa có major mới hơn → **không dùng cho #2** |
| RDS Proxy | **chưa có** | — | tùy chọn (§7), có phí |

---

## 2. Thước đo "0 request rớt" — đo ở đâu cho đúng

> 🔑 **Bài học từ sự cố 0012 (Mandate #8):** công thức SLO của `checkout` đo *tỉ lệ lỗi trong số request TỚI
> ĐƯỢC checkout*. Khi checkout chết hẳn (0 span) công thức báo ~100% **dù khách fail hoàn toàn** — một
> **điểm mù**. Với #9 (bar = 0 lỗi tuyệt đối) **không được** dựa vào riêng công thức đó.

**Ba tầng đo, phải cùng = 0 trong mỗi cửa sổ thay đổi:**

1. **Locust (thước đo khách trực tiếp):** `Number of Failures` phải **giữ nguyên = 0** suốt cửa sổ. Đây là
   bằng chứng đầu tiên và mạnh nhất — chính là "khách" của bài.
2. **frontend-proxy (Envoy) ở biên:** đếm response **non-2xx** trên route khách
   (`sum(rate(envoy_cluster_upstream_rq{envoy_response_code!~"2.."}[1m]))`) = 0. Đo ở biên tránh điểm mù span.
3. **Theo store (bằng chứng zero-loss, không chỉ zero-downtime):**
   - RDS: DB stats của `otelsql`/Npgsql — số lỗi query = 0; sau mỗi thao tác đối chiếu **đếm đơn** (parity).
   - MSK: consumer **LAG** hai group về 0; `accounting` không mất đơn (offset commit thủ công, REL-09).
   - Valkey: counter lỗi thao tác cart = 0.

**Điều kiện tải:** giữ `load-generator` chạy **liên tục** qua toàn bộ demo (khuyến nghị nâng tạm
`LOCUST_USERS` 10→30 để phép chứng minh có ý nghĩa; **không** nâng cao hơn để khỏi tự tạo nhiễu chi phí
Bedrock/MSK — xem §8). ⚠️ **Ảnh hưởng:** nâng users làm tăng nhẹ tải CPU pod + chi phí data-transfer/token
trong cửa sổ demo; hết demo trả về 10.

---

## 3. NỀN TẢNG BẮT BUỘC — App chịu được blip kết nối (Yêu cầu #5)

Mọi thao tác #1–#4 đều làm **kết nối tới store đổi trong tích tắc** (failover, switchover, reboot, đổi
credential). Nếu app không nuốt được thì **#1–#4 không thể đạt "0 rớt"**. Vì vậy #5 **làm trước tiên**, mỗi
thay đổi **gated bằng env / mặc định no-op** (đúng kỷ luật Mandate #8: tách "deploy code" khỏi "thao tác").

### 3.1 Hiện trạng từng service (đã rà code)

| Service | Ngôn ngữ/driver | Posture hiện tại | Cần làm |
|---|---|---|---|
| `product-catalog` | Go / `database/sql`+lib/pq | Pool có giới hạn (20/10, lifetime 5′) **nhưng query gọi 1 phát, KHÔNG retry** → blip = rớt browse | **Thêm retry** quanh query |
| `product-reviews` | Python / psycopg2 pool | Pool 1–10, `_run_query` lỗi là `raise`, **không retry**, và **không loại bỏ connection chết** khỏi pool sau failover | **Thêm retry + huỷ conn hỏng** |
| `cart` | .NET / StackExchange.Redis | **Tốt sẵn**: `abortConnect=false`, `ConnectRetry=30`, `ExponentialRetry`, handler `ConnectionRestored/Failed`, `KeepAlive=180` | **Verify** + retry mỏng quanh thao tác |
| `accounting` | .NET / Npgsql+EF | **Bền sẵn** ở tầng vòng lặp consumer: ghi lỗi → không commit offset → `Seek` + ngủ 2s → thử lại → **không mất đơn** | Optional `EnableRetryOnFailure` cho gọn |
| `checkout` | Go / sarama | **Tốt sẵn** cho produce: `WaitForAll`+`Idempotent`+`Retry.Max=3`+`MaxOpenRequests=1`, `Timeout=5s` | **Nâng `Retry.Max`** nếu chọn nâng MSK (§5) |

### 3.2 Vá cụ thể

**`product-catalog` (Go)** — bọc các hàm `loadProductsFromDB` / `getProductFromDB` / `searchProductsFromDB`
bằng retry ngắn cho lỗi kết nối tạm thời (đóng băng ~vài trăm ms, không kéo dài request khách):

```go
// retryTransient thử lại thao tác DB khi gặp lỗi kết nối tạm thời (failover/reboot/switchover).
// Chỉ retry lỗi mạng/driver.ErrBadConn, KHÔNG retry lỗi logic (sql.ErrNoRows...).
func retryTransient(ctx context.Context, op func() error) error {
    const attempts = 4
    backoff := 100 * time.Millisecond
    var err error
    for i := 0; i < attempts; i++ {
        if err = op(); err == nil || !isTransient(err) {
            return err
        }
        select {
        case <-ctx.Done(): return ctx.Err()
        case <-time.After(backoff):
        }
        backoff *= 2 // 100 → 200 → 400 → 800ms, tổng < 1.5s < timeout gRPC
    }
    return err
}
```
`isTransient`: bắt `driver.ErrBadConn`, `net.Error`, và mã lỗi PG `57P01/57P03` (admin shutdown / cannot
connect now). Kết hợp `db.SetConnMaxLifetime` **hạ 5′ → 60s** để pool thải nhanh connection trỏ endpoint cũ
sau switchover.

**`product-reviews` (Python)** — `_run_query` retry + **loại connection chết** khỏi pool (đừng trả conn hỏng
về pool):

```python
def _run_query(query, params, attempts=4):
    backoff = 0.1
    for i in range(attempts):
        conn = _connection_pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params); rows = cur.fetchall()
            conn.commit(); _connection_pool.putconn(conn); return rows
        except psycopg2.OperationalError:              # lỗi kết nối → conn đã hỏng
            _connection_pool.putconn(conn, close=True)  # KHÔNG tái dùng conn chết
            if i == attempts-1: raise
            time.sleep(backoff); backoff *= 2
        except Exception:
            conn.rollback(); _connection_pool.putconn(conn); raise
```

**`cart` (.NET)** — posture đã tốt; chỉ thêm retry mỏng (2–3 lần) quanh `HashGet/HashSet` để nuốt đúng
khoảnh khắc failover ElastiCache (~<15s), và **verify** bằng elasticache failover test (§5.3).

**`accounting` (.NET)** — thêm cho gọn (không bắt buộc):
`optionsBuilder.UseNpgsql(cs, o => o.EnableRetryOnFailure(5, TimeSpan.FromSeconds(2), null))`.

### 3.3 ⚠️ Ảnh hưởng workload của bước nền tảng

| Hành động | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| Rebuild image + rollout 4 service (retry) | Rolling update qua ArgoCD/Argo Rollouts, **`maxUnavailable:0`** → **0 request rớt** (đã chứng minh ở Mandate #3) | Deploy khi tải bình thường; các thay đổi **no-op về hành vi** cho tới khi có blip thật |
| Hạ `ConnMaxLifetime` 5′→60s (product-catalog) | Mở connection mới thường xuyên hơn (nhẹ), tổng connection vẫn ≤ pool cap 20 | RDS `max_connections` dư (DB 38MB, tải thấp) |

> Đây đều là thay đổi **thuần app**, **$0**, và đúng thứ directive gọi tên: *"retry / connection pool"*. RDS
> Proxy (tùy chọn, có phí) bàn ở §7.

---

## 4. YÊU CẦU #1 — Online schema migration dưới tải (tâm điểm)

**Nguyên tắc expand → backfill → dual-write/read → contract:** ở mọi thời điểm, **schema tương thích với CẢ
phiên bản app đang chạy lẫn phiên bản mới** → không có khoảnh khắc nào app hỏi một cột không tồn tại → **0
rớt**. Tuyệt đối tránh mọi DDL lấy khoá `ACCESS EXCLUSIVE` trên bảng có traffic.

> **Thực tế hệ thống này:** không có bảng nào **vừa lớn vừa nằm trên đường ĐỌC của khách**. Nên demo tách 2
> bảng để phủ trọn từ vựng của directive:
> - **`accounting.orderitem`** (395k dòng, **có traffic GHI** liên tục) → chứng minh **no-lock ở quy mô lớn** + backfill + dual-write.
> - **`catalog.products`** (đường **ĐỌC của khách** qua product-catalog) → chứng minh **dual-read + contract** + tương thích ngược.

### 4.1 Bảng lớn có traffic ghi — `accounting.orderitem` (thêm cột + index, KHÔNG lock)

Thêm cột `created_at timestamptz` (bảng hiện **không có mốc thời gian** — một thiếu sót thật) + index phục vụ
báo cáo, trên bảng **395k dòng đang được `accounting` ghi liên tục**.

| Phase | Lệnh / hành động | Vì sao KHÔNG lock |
|---|---|---|
| **Expand** | `ALTER TABLE accounting.orderitem ADD COLUMN created_at timestamptz;` (nullable, **không** default) | PG chỉ đổi **metadata** — tức thời, không rewrite, khoá chỉ giữ mili-giây |
| **Dual-write** | Deploy `accounting` ghi `created_at = now()` cho đơn mới (gated env `ORDERITEM_WRITE_CREATED_AT`) | App đang ghi cả cột mới; đơn cũ tạm NULL |
| **Backfill** | `UPDATE ... SET created_at = <sentinel> WHERE created_at IS NULL` theo **lô 5–10k** (vòng lặp), nghỉ giữa lô | Lô nhỏ → mỗi UPDATE khoá **theo dòng** ngắn, không lock cả bảng, WAL không dồn |
| **Enforce NOT NULL** (không full-scan lock) | `ALTER TABLE ... ADD CONSTRAINT oi_created_at_nn CHECK (created_at IS NOT NULL) NOT VALID;` rồi `VALIDATE CONSTRAINT oi_created_at_nn;` | `NOT VALID` chỉ thêm metadata; `VALIDATE` lấy khoá **`SHARE UPDATE EXCLUSIVE`** — **không chặn đọc/ghi** |
| **Index** | `CREATE INDEX CONCURRENTLY idx_orderitem_created_at ON accounting.orderitem(created_at);` | `CONCURRENTLY` chỉ lấy `SHARE UPDATE EXCLUSIVE` — đọc/ghi vẫn chạy |

> ⚠️ **Ảnh hưởng workload:**
> - **Nếu làm ĐÚNG (trên):** `accounting` tiếp tục ghi bình thường, **MSK LAG giữ 0**, **checkout không hề
>   liên quan** (được Kafka tách khỏi accounting). Khách **không thấy gì**.
> - **Nếu làm SAI (cảnh báo, KHÔNG làm):** `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT <hằng động>`, hay
>   `ALTER COLUMN ... TYPE`, hay `CREATE INDEX` (không CONCURRENTLY) → lấy **`ACCESS EXCLUSIVE`** → **chặn
>   `accounting` ghi** → đơn dồn ở Kafka → **LAG tăng**, kế toán trễ (đơn **không mất** nhờ REL-09, nhưng vi
>   phạm tinh thần "không gián đoạn"). `CREATE INDEX CONCURRENTLY` có thể **thất bại để lại index invalid** →
>   phải `DROP INDEX` rồi tạo lại (không ảnh hưởng khách).
> - **Backfill:** UPDATE hàng loạt sinh WAL + có thể tạo bloat → chạy **lô nhỏ, giờ tải thấp trong cửa sổ**,
>   theo dõi `ReplicaLag` (Multi-AZ) và autovacuum. Với 395k dòng, vài phút là xong.

### 4.2 Đường đọc của khách — `catalog.products` (`categories` CSV → `text[]`, dual-read + contract)

`product-catalog` đọc `catalog.products` **mỗi lần browse** và hiện tự tách chuỗi CSV `categories` bằng tay
(`strings.Split` trong `parseProductRow`). Chuyển sang kiểu `text[]` chuẩn — bài dual-read tương thích ngược.

```
Expand   : ALTER TABLE catalog.products ADD COLUMN categories_arr text[];
Backfill : UPDATE catalog.products SET categories_arr = string_to_array(categories, ',')
           WHERE categories_arr IS NULL;                       -- 10 dòng, tức thời
Dual-read: deploy product-catalog đọc COALESCE(categories_arr, string_to_array(categories,','))
           → chạy ĐÚNG dù backfill xong hay chưa, dù cột cũ còn hay đã bỏ  (tương thích ngược 2 chiều)
Verify   : browse xanh 100%, Locust failures = 0, so số danh mục trước/sau
Contract : (sau khi bake ≥1 ngày) ALTER TABLE catalog.products DROP COLUMN categories;
```

> ⚠️ **Ảnh hưởng workload:**
> - Mỗi phase **tương thích ngược**: không có thời điểm nào app đang chạy hỏi cột đã bị bỏ → **0 rớt browse**.
> - **Điểm không quay lui** = phase **Contract (`DROP COLUMN`)**. Chỉ chạy khi app phiên bản dual-read đã phủ
>   **100% pod** và đã bake đủ lâu; trước đó revert = đổi lại đọc cột cũ (còn nguyên). `DROP COLUMN` bản thân
>   là metadata (nhanh, không rewrite) nhưng **không thể hoàn tác** nếu app cũ còn cần cột đó.
> - Bảng chỉ 10 dòng → **không** rủi ro lock; giá trị demo nằm ở **phối hợp app–DB + tương thích ngược**, đúng
>   thứ directive nhấn mạnh (*"bài app + DB phối hợp, không có tooling làm hộ"*).

### 4.3 Chứng minh & rollback #1
- **Error=0:** Locust failures = 0 + Envoy non-2xx = 0 suốt cả 2 chuỗi; MSK LAG=0; đối chiếu đếm dòng
  trước/sau (chỉ tăng do traffic, không mất).
- **Rollback:** mọi phase trước Contract đều lùi được bằng deploy app cũ / để cột NULL. Sau Contract cần
  PITR (nên chỉ Contract sau bake dài).

---

## 5. YÊU CẦU #2 — Nâng version lớn, zero-downtime

### 5.1 Chọn chính: RDS PostgreSQL **17 → 18** bằng **Blue/Green Deployment**

Major upgrade tại chỗ của RDS **có downtime** (vài phút instance không phục vụ) → **không đạt #9**. Cách
zero-downtime chuẩn là **RDS Blue/Green**:

1. Tạo Blue/Green: RDS dựng môi trường **green** (bản sao chạy **18.4**) đồng bộ với blue qua **logical
   replication**. Blue (17.9) **vẫn phục vụ khách bình thường** suốt lúc này.
2. **Test trên green** (đúng schema sau §4, chạy thử query, kiểm extension tương thích PG18).
3. **Switchover** (~<1 phút): RDS chặn ghi trên blue trong giây lát, chờ green bắt kịp, rồi **đổi tên
   endpoint** — green nhận đúng hostname production `techx-tf3-postgres.czwcs2ocww3q…`. **App không phải đổi
   cấu hình gì** — chỉ thấy kết nối reset một nhịp.

> ⚠️ **Ảnh hưởng workload (bắt buộc nêu):**
> - **Cửa sổ switchover ~<1 phút** có một nhịp **ghi bị chặn + kết nối hiện tại bị ngắt**. Tác động tới từng
>   service:
>   - `product-catalog` / `product-reviews` (đọc): kết nối rớt → **retry ở §3 nuốt trong <1.5s** → khách
>     không thấy lỗi. **Đây chính là lý do §3 phải xong trước.**
>   - `accounting` (ghi): write fail nhất thời → vòng lặp consumer **không commit, thử lại** → **không mất
>     đơn**, chỉ trễ vài giây (hậu trường, khách không thấy).
>   - `checkout`: **không đụng RDS** → không ảnh hưởng.
> - **Chi phí:** trong lúc BG tồn tại, **chạy song song 2 bộ DB** (blue + green) → tốn thêm ~cấu hình RDS
>   trong **vài giờ/ngày** demo (prorated, ~vài USD). Xoá blue sau khi xác nhận green ổn.
> - **Rollback:** sau switchover, **blue (17.9) vẫn được RDS giữ lại** (tách riêng) → nếu green lỗi, trỏ
>   ngược về blue. Chỉ xoá blue khi đã chắc chắn.

### 5.2 Phương án thay thế (an toàn hơn về "khoảnh khắc"): MSK **3.9 → 4.0** rolling

MSK nâng version theo **rolling**: reboot **từng broker một**, leader partition dời sang broker khác. Với
**RF=3 / isr=2**, mất 1 broker tại một thời điểm **vẫn produce/consume bình thường**.

> ⚠️ **Ảnh hưởng workload:**
> - Mỗi broker reboot ~10–20 phút, lần lượt 3 broker → tổng ~30–60 phút có **under-replicated partitions**
>   (bình thường trong rolling). `checkout` (producer `acks=all`) khi leader dời sẽ retry — **nâng
>   `Producer.Retry.Max` 3→10 + tăng `Producer.Timeout`** trước khi nâng để chắc chắn nuốt được cửa sổ
>   chuyển leader; consumer `accounting`/`fraud` rebalance vài giây.
> - **So sánh:** MSK rolling **không có "khoảnh khắc switchover"** như RDS BG (rủi ro thấp hơn) nhưng **lâu
>   hơn** và cần verify client retry. RDS BG **nhanh gọn** nhưng có 1 nhịp switchover cần §3 đỡ.
> - **Khuyến nghị:** chọn **RDS 17→18 (BG)** làm bài chính (thể hiện đúng "nâng version lớn của DB" — chỗ khó
>   nhất), giữ **MSK 3.9→4.0** làm phương án dự phòng/bổ sung nếu mentor muốn thấy thêm hoặc nếu test PG18
>   trên green phát hiện vấn đề tương thích.

### 5.3 Chứng minh & rollback #2
Locust failures=0, Envoy non-2xx=0 suốt cửa sổ; sau upgrade so đếm đơn (không mất). RDS: giữ blue để lùi.
MSK: nâng version là một chiều nhưng rolling nên không cần lùi; nếu client lỗi thì đã lộ ở broker đầu tiên →
dừng, sửa retry, tiếp.

---

## 6. YÊU CẦU #3 — Đổi tham số cần reboot, zero-downtime

**Thay đổi chọn (hữu ích thật):** thêm `pg_stat_statements` vào `shared_preload_libraries` của param group
`techx-tf3-postgres17`. Đây là tham số **static** → **bắt buộc reboot** mới có hiệu lực (đúng loại directive
yêu cầu), và mở khoá quan sát top-query cho tối ưu sau này.

**Cách zero-downtime trên Multi-AZ = reboot-with-failover:**
1. Sửa param trong `techx-tf3-postgres17` (qua Terraform, đúng kỷ luật IaC) → trạng thái `pending-reboot`.
2. `reboot-db-instance --force-failover`: RDS **promote standby ở AZ kia** thành primary (đã có sẵn, nóng),
   primary cũ reboot để nạp param. Endpoint **giữ nguyên**, chỉ trỏ sang node mới.

> ⚠️ **Ảnh hưởng workload:**
> - **Failover Multi-AZ ~60–120 giây**: mọi kết nối hiện tại tới primary cũ **bị ngắt**; connection mới trỏ
>   sang primary mới.
>   - đọc (catalog/reviews): **retry §3 nuốt** (failover < vài chục giây, nằm trong ngân sách retry/pool).
>   - ghi (accounting): thử lại, **không mất đơn**.
>   - checkout: không đụng.
> - **`pg_stat_statements` sau khi bật** tốn RAM nhỏ (`pg_stat_statements.max` mặc định) + chút CPU thu thập
>   — không đáng kể trên tải hiện tại.
> - **Rollback:** bỏ param khỏi group → reboot-with-failover lần nữa (cùng chi phí ~1 nhịp failover).

> 📌 Vì sao **RDS** chứ không ElastiCache cho #3: ElastiCache đang dùng **param group mặc định**
> (`default.valkey9`) — **không sửa được**; muốn đổi param phải tạo custom group trước. RDS đã có sẵn custom
> group nên là nơi tự nhiên nhất để demo #3.

---

## 7. YÊU CẦU #4 — Xoay credential live, không restart gây rớt

### 7.1 Vấn đề gốc (phát hiện khi rà `datastores-secrets.yaml`)
ExternalSecret `postgres-connection` đọc `username`+`password` **thẳng từ secret master do RDS quản**
(`rds!db-78563b84-…`) → **app nối RDS bằng chính user MASTER**, và nhận qua **biến môi trường cố định lúc pod
start** (`DB_CONNECTION_STRING`). RDS-managed master password **tự xoay (mặc định 7 ngày)**; ESO re-sync
K8s secret nhưng **app không đọc lại env** → lần xoay tới **app gãy kết nối mới** (connection cũ trụ tới khi
pool recycle rồi cũng đứt). **Đây là rủi ro thật + vừa dùng superuser (kém bảo mật).**

### 7.2 Giải pháp tối ưu: **RDS IAM database authentication** (bỏ hẳn mật khẩu tĩnh)

Đây là câu trả lời "trưởng thành" nhất và **$0**: app **không giữ mật khẩu nào cả**, dùng **token IAM ngắn
hạn (15 phút)** làm password. "Xoay credential" trở thành **vốn dĩ liên tục** — không có mật khẩu tĩnh để mà
gãy.

**Chuẩn bị (làm trước, mỗi bước gated, xem ảnh hưởng bên dưới):**
1. **Tạo user DB tối thiểu quyền** (bỏ dùng master): `catalog_ro`/`reviews_ro` (chỉ `SELECT`),
   `accounting_rw` (ghi schema accounting); `GRANT rds_iam` cho cả ba. *(Ảnh hưởng: tạo role + GRANT là
   metadata, **không lock bảng app**, khách không thấy.)*
2. **Bật IAM auth trên RDS** (`iam_database_authentication_enabled=true`) — modify **áp dụng ngay, không
   reboot**. *(Ảnh hưởng: none tới kết nối hiện tại.)*
3. **IRSA** cho 3 pod: quyền `rds-db:connect` tới đúng resource `dbuser`.
4. **App sinh token IAM làm password** (dùng cơ chế "password provider" có sẵn của mỗi driver):
   - `accounting` (.NET/Npgsql): `NpgsqlDataSourceBuilder.UsePeriodicPasswordProvider(...)` — Npgsql **gọi
     lại định kỳ** để lấy password mới → hợp IAM token hoàn hảo, **không cần restart**.
   - `product-catalog` (Go): custom `driver.Connector` sinh token qua `auth.BuildAuthToken` mỗi lần mở
     connection mới (kết hợp `ConnMaxLifetime=60s` ở §3 → token luôn tươi).
   - `product-reviews` (Python): bọc `getconn` để build DSN với `generate_db_auth_token` (boto3).

**Demo #4 (dưới tải):** không còn "mật khẩu" để xoay — thay vào đó chứng minh **token tự hết hạn & tái sinh
live**: ép token cũ hết hạn / trigger tái sinh, quan sát app **mở connection mới bằng token mới, 0 rớt**;
đồng thời **xoay secret master** (thứ Proxy/ai đó vẫn cần) để cho thấy app **không còn phụ thuộc** nó nữa.

> ⚠️ **Ảnh hưởng workload của việc cutover sang IAM auth:**
> - Đổi cách app lấy credential = **rebuild + rollout 3 service**. Làm **rolling `maxUnavailable:0`** → **0
>   rớt**. Mỗi bước gated: deploy code "biết dùng IAM" trước (vẫn chạy password cũ), lật sang IAM bằng 1 cờ
>   env → lỗi thì lật lại ~1 phút.
> - Sau cutover, **thu hồi quyền login của master cho app** → giảm bề mặt tấn công (trụ Security).
> - IAM auth có **giới hạn ~200 kết nối mới/giây/instance** — tải hiện tại (pool nhỏ, DB 38MB) **thừa sức**.

### 7.3 Hai phương án thay thế (ghi rõ đánh đổi)

| Phương án | Được gì | Mất gì |
|---|---|---|
| **A. App-user tĩnh + Secrets Manager rotation "multi-user (alternating)" + đọc secret từ FILE mount, hot-reload pool** | $0, không cần IAM; overlap 2 mật khẩu → luôn có 1 cái valid → **0 auth-fail** | Vẫn còn mật khẩu tĩnh; phải code hot-reload pool ở 3 ngôn ngữ |
| **B. RDS Proxy + IAM** | Proxy **hấp thụ luôn failover/switchover** (đỡ gánh nặng §3 cho #2/#3), giữ pool phía DB | **+~$22/tháng** (0.015 USD/vCPU-h × 2 vCPU); thêm 1 hop + 1 cutover |

> **Khuyến nghị:** dùng **IAM auth trực tiếp (§7.2)** làm chính vì **$0 + bảo mật nhất + hợp ràng buộc ngân
> sách**. Cân nhắc **RDS Proxy (B)** *chỉ khi* muốn một lớp hấp thụ blip mạnh hơn cho #2/#3 và ngân sách cho
> phép — **có thể tự bù**: dọn VPC endpoint (kế hoạch cost đã có, −$113/tháng) **thừa sức** gánh $22/tháng
> Proxy, tổng vẫn giảm. Xem §8.

---

## 8. Ngân sách & đánh đổi (ràng buộc directive: "trong ngân sách")

TF3 **đang vượt trần** ($426/tuần / trần $300 — xem [`cost-breakdown-2026-07-22.md`](../cost-breakdown-2026-07-22.md)),
nên #9 **ưu tiên phương án $0**:

| Hạng mục #9 | Chi phí tăng thêm | Ghi chú |
|---|---|---|
| §3 retry, §4 IAM auth, §1 schema, §6 param | **$0** | thuần app / thao tác managed sẵn có |
| §5 RDS Blue/Green | ~vài USD **một lần** | 2 bộ DB song song trong vài giờ/ngày demo, xoá blue sau |
| §5 MSK 3.9→4.0 | **$0** | rolling trên cụm sẵn có |
| §7 RDS Proxy (tùy chọn) | **+$22/tháng** | chỉ nếu chọn phương án B — **tự bù** bằng dọn VPC endpoint (−$113/th) |

> **Kết luận:** giải pháp chính **không làm ngân sách xấu đi**. Nếu mentor muốn "chuẩn SRE tối đa" bằng RDS
> Proxy thì kèm luôn dọn VPC endpoint để **net vẫn giảm chi**.

---

## 9. Trình tự thực thi buổi demo (dưới tải, error=0)

> Giữ `load-generator` chạy **liên tục** từ đầu đến cuối. Trước mỗi cửa sổ, mở 3 bảng đo (Locust failures /
> Envoy non-2xx / store health) và **chỉ sang cửa sổ kế khi cả ba đang = 0**.

| Bước | Nội dung | Cửa sổ | Bằng chứng "0 rớt" |
|---|---|---|---|
| 0 | Deploy **nền tảng §3** (retry/reconnect) + **§7.2 code IAM** (gated, no-op) | rolling `maxUnavailable:0` | Locust=0 khi rollout |
| 1 | **#1 Schema**: expand→backfill→dual-write `orderitem`; expand→backfill→dual-read `products` | vài deploy | Locust=0, LAG=0, đếm dòng khớp |
| 2 | **#4 Cred**: lật app sang **IAM auth**, rồi trình token tái sinh live + xoay master | ~phút | Locust=0, 0 auth-fail |
| 3 | **#3 Param**: thêm `pg_stat_statements` → **reboot-with-failover** | ~60–120s failover | Locust=0 (retry nuốt) |
| 4 | **#2 Version**: **RDS 17→18 Blue/Green** → switchover | ~<1 phút switchover | Locust=0, đếm đơn khớp |
| 5 | (tuỳ chọn) **#2b MSK 3.9→4.0** rolling | ~30–60 phút | Locust=0, LAG=0 |
| 6 | Contract phase #1 (`DROP COLUMN products.categories`) **sau bake** | tức thời | — |

Thứ tự có chủ đích: **nền tảng trước**, rồi các thao tác **từ rủi ro thấp → cao** (schema → cred → param →
version), để nếu có sự cố thì dừng sớm ở bước ít hại nhất.

---

## 10. Ràng buộc bất biến (nhắc trước khi chạm hạ tầng thật)

- **KHÔNG** đụng/vô hiệu hoá `flagd`; `/flagservice` trong Envoy giữ nguyên; filter `envoy.filters.http.fault`
  giữ nguyên (hạ tầng BTC bơm sự cố).
- **Directive #1 giữ nguyên:** storefront public qua CloudFront, cổng vận hành private (SSM/Cloudflare).
- **Secret không vào file tracked**: token IAM sinh runtime; mật khẩu (nếu còn) qua Secrets Manager →
  ExternalSecret, **không** hardcode.
- **IaC**: mọi đổi RDS/param group qua **Terraform** (`infra/live/production`), `plan -out` rồi `apply`, **không**
  `apply -auto-approve`; deploy app qua **GitOps/ArgoCD**, base nhánh `main`.
- **Verify chart** bằng `helm template` (schema `additionalProperties:false`) trước commit.

---

## 11. Bảng tập trung — mọi hành động CHẠM workload & ảnh hưởng

| Hành động | Chạm gì | Ảnh hưởng khách | Vì sao vẫn "0 rớt" |
|---|---|---|---|
| Rollout app (§3/§4/§1 dual-*) | pod restart lần lượt | không | `maxUnavailable:0` + graceful (Mandate #3) |
| `ADD COLUMN` nullable, `NOT VALID`+`VALIDATE`, `INDEX CONCURRENTLY` | RDS (orderitem 395k) | không | không lấy `ACCESS EXCLUSIVE`; accounting ghi tiếp, LAG=0 |
| Backfill UPDATE theo lô | RDS ghi + WAL | không | lô nhỏ, khoá theo dòng ngắn; theo dõi ReplicaLag/autovacuum |
| `DROP COLUMN` (contract) | RDS (products) | không | chỉ sau khi app dual-read phủ 100% + bake; **không quay lui** |
| **reboot-with-failover** (#3) | RDS Multi-AZ | ngắt kết nối ~60–120s | retry §3 nuốt đọc; accounting thử lại (không mất đơn) |
| **Blue/Green switchover** (#2) | RDS | ngắt kết nối + chặn ghi ~<1 phút | retry §3 nuốt; blue giữ lại để lùi; endpoint đổi tự động |
| **MSK rolling upgrade** (#2b) | MSK từng broker | under-replicated ~30–60′ | RF=3/isr=2 chịu mất 1 broker; producer retry (nâng `Retry.Max`) |
| Cutover sang **IAM auth** (#4) | 3 app | không | rolling `maxUnavailable:0`, gated cờ env |
| Bật IAM auth / tạo role / bật `pg_stat_statements` | RDS metadata | không | modify động (không reboot) / GRANT không lock bảng app |
| Nâng `LOCUST_USERS` 10→30 | load-generator | (tạo tải, không phải khách thật) | trả về 10 sau demo; tăng nhẹ CPU + chi phí token/transfer |

---

## 12. Việc cần làm để sẵn sàng demo (checklist)

- [ ] §3: PR retry cho product-catalog (Go) + product-reviews (Python); verify cart/checkout; hạ ConnMaxLifetime.
- [ ] §7: Terraform bật `iam_database_authentication_enabled`; tạo user tối thiểu quyền + `rds_iam`; IRSA
      `rds-db:connect`; PR password-provider 3 service; ExternalSecret trỏ app-user (không master).
- [ ] §4-schema: script expand/backfill/validate cho `orderitem`; PR dual-read `products`.
- [ ] §6: Terraform thêm `pg_stat_statements` vào `techx-tf3-postgres17`.
- [ ] §5: quy trình `create-blue-green-deployment` + kiểm PG18 (extension/compat) trên green; (tuỳ chọn) nâng
      `Producer.Retry.Max` checkout cho MSK.
- [ ] Đo: dashboard Locust failures + Envoy non-2xx + MSK LAG + đếm đơn, mở sẵn cho mentor xem **=0**.
- [ ] ADR ký tên (`docs/adr/`) cho quyết định IAM-auth + Blue/Green; runbook thao tác từng bước.

---

*Ký: CDO02 (Reliability + Cost Optimization). Phối hợp cần: CDO01 (Security — IAM/IRSA/least-priv DB user),
AIO02 (theo dõi store trong lúc thao tác).*
*Mọi con số hạ tầng trong doc đã verify live 28/07/2026 (read-only, profile `prod`).*
