# Runbook — schema `copilot.user_memory` (DB request AIE2)

**Yêu cầu gốc:** AIE2 — "[DB Request] Tạo Schema Long-term User Memory — Shopping Copilot", 28/07/2026.
**Thực hiện:** CDO02 · **Ngày:** 30/07/2026
**Đích:** RDS `techx-tf3-postgres` (`ap-southeast-1`, Multi-AZ), DB `otel`, schema `copilot`.

Mục đích của AIE2: chuyển Long-term User Memory của shopping-copilot từ Valkey TTL-30-ngày sang
lưu bền trong Postgres, và có chỗ để thực thi GDPR right-to-delete.

---

## 1. Cách chạy

Migration đi qua **ArgoCD**, không `psql` tay, không `kubectl apply` tay:

| Thành phần | Đường dẫn |
|---|---|
| Job | [`gitops/jobs/copilot-user-memory/migration-job.yaml`](../../gitops/jobs/copilot-user-memory/migration-job.yaml) |
| NetworkPolicy | [`gitops/jobs/copilot-user-memory/networkpolicy.yaml`](../../gitops/jobs/copilot-user-memory/networkpolicy.yaml) |
| Application | [`gitops/apps/copilot-user-memory-migration-app.yaml`](../../gitops/apps/copilot-user-memory-migration-app.yaml) |

Merge PR vào `main` → app-of-apps `techx-corp-bootstrap` nhặt Application mới → Application
`copilot-user-memory-migration` sync → Job chạy một lần.

Theo dõi:

```bash
kubectl -n argocd get application copilot-user-memory-migration
```

```bash
kubectl -n techx-tf3 logs job/copilot-user-memory-schema-migration-r2
```

Log kết thúc bằng `SCHEMA VERIFICATION OK` là xong. Nếu có dòng `[BAD]`, Job exit 1 và log liệt
kê đúng những check đã hỏng.

**Muốn chạy lại (ví dụ sửa SQL):** PodTemplate của Job là immutable — phải đổi tên Job thành
`-r3`, không sửa tại chỗ. Mọi statement đều `IF NOT EXISTS` / `OR REPLACE` nên chạy lại an toàn.

### ⚠️ Lần chạy đầu (`-r1`) treo vì `default-deny-all` — đã xử lý

`default-deny-all` (`podSelector: {}` = mọi pod trong namespace, cả Ingress+Egress) được promote
ngày 29/07. Pod của Job không khớp policy allow nào → **mất DNS** → `psycopg2.connect()` treo im
lặng, log **rỗng hoàn toàn** (dòng print đầu tiên nằm sau `connect()`).

Đo được trên production: `-r1` treo >5 phút; exec vào pod thì
`socket.gethostbyname(<rds-endpoint>)` trả `gaierror [Errno -3] Try again` sau 5,2s.

Đúng cái bẫy mà [`gitops/aiops-engine/cronjob.yaml`](../../gitops/aiops-engine/cronjob.yaml) đã
ghi lại: workload chạy một lần / theo lịch dễ bị bỏ sót khi default-deny được promote, vì nó
không chạy liên tục nên không ai thấy nó đứt mạng.

Đã xử lý bằng 3 việc:

1. `networkpolicy.yaml` mở **đúng** DNS + 5432 cho riêng pod của Job, dùng `ipBlock` cho RDS
   (không phải `podSelector` — chính lỗi đã gây outage 20/07, postmortem 0012). Không nới lỏng
   `default-deny-all`, không đụng policy nào của CDO01.
2. `sync-wave`: netpol `0` → Job `1`, để policy có trước khi pod start.
3. Script in một dòng **trước** khi connect + `connect_timeout=15` → lần sau bị chặn mạng thì
   báo lỗi to rõ thay vì treo không dấu vết.

---

## 2. Ba điểm lệch có chủ đích so với SQL trong request

1. **`CREATE TRIGGER` → `CREATE OR REPLACE TRIGGER`.** Bản gốc không idempotent; với
   `backoffLimit: 2`, lần retry thứ 2 sẽ chết vì `trigger already exists`. RDS đang chạy
   **PostgreSQL 17.9** (verify 30/07 bằng `aws rds describe-db-instances`) nên cú pháp
   `CREATE OR REPLACE TRIGGER` (PG14+) dùng được.

2. **GRANT giữ nguyên nhưng là no-op — đừng báo cáo là "đã least-privilege".** `otelu` chính là
   **RDS master user** (`MasterUsername=otelu`, verify 30/07). Schema và bảng do chính nó tạo nên
   nó là OWNER, mà owner trong PostgreSQL mặc nhiên có toàn quyền. `GRANT ... TO otelu` vì thế
   không thu hẹp được gì. Đây là đúng tình trạng đã gặp với `reviews.product_summaries` và
   `reviews.fidelity_audit`. Muốn cô lập thật thì phải tạo role riêng cho copilot + đổi owner —
   việc lớn hơn, cần bàn riêng.

3. **Bỏ `GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA copilot`.** Bảng không có cột
   serial/identity nên schema `copilot` không sinh sequence nào. Câu lệnh vô hại nhưng vô nghĩa.

---

## 3. Job verify những gì

Ngoài việc chạy 8 statement, Job tự kiểm chứng rồi mới báo thành công:

- **Cột**: đủ 7 cột, đúng kiểu (`VARCHAR(128)`, 4× `jsonb`, 2× `timestamptz`), đúng `NOT NULL`,
  và cả 6 cột có DEFAULT đều thật sự có default. `CREATE TABLE IF NOT EXISTS` vẫn "thành công"
  khi bảng cũ sai schema, nên `to_regclass` một mình không đủ để kết luận.
- **Primary key** = `user_id`.
- **Index**: cả hai tồn tại, `indisvalid=true`, và `idx_user_memory_preferences` đúng là **GIN**.
- **Trigger**: đúng 1 trigger user-defined, trỏ đúng hàm `set_updated_at`, đang enabled.
- **Grant**: `otelu` có đủ SELECT/INSERT/UPDATE/DELETE (in kèm NOTE về owner ở trên).
- **Probe thực tế trong transaction rồi ROLLBACK** (không để lại rác): upsert một row, đọc lại
  bằng toán tử containment `@>` (đường mà GIN index phục vụ), UPDATE để chứng minh trigger đẩy
  `updated_at` lên và **không** đụng `created_at`, rồi DELETE để chứng minh đường GDPR chạy được.

---

## 4. ⚠️ Việc AIE2 phải làm ở phía app — `search_path`

`shopping-copilot` kết nối RDS bằng `DB_USER`/`DB_PASSWORD` rời (Secret `shopping-copilot-db`),
và `connect.py` set **`search_path=catalog,reviews,public`** — **không có `copilot`**.

⇒ Query kiểu `SELECT ... FROM user_memory` sẽ fail `relation "user_memory" does not exist`.
Chọn một trong hai:

- **Nên:** luôn ghi tên đủ — `copilot.user_memory` (như đúng SQL trong access pattern của request).
- Hoặc thêm `copilot` vào `search_path` trong `connect.py`.

Bảng đã sẵn sàng cho smoke test của AIE2 qua tunnel `localhost:5433`.

---

## 5. Đường lui

Thay đổi là **additive thuần** — tạo schema mới, không đụng `catalog` / `reviews` / `public`,
không đụng dữ liệu AIOps hay OpenTelemetry. Muốn gỡ:

```sql
DROP SCHEMA copilot CASCADE;
```

Rủi ro dung lượng không đáng kể: ~2 KB/row × ~10k user ≈ **20 MB** ban đầu, tăng ~50 MB/năm,
trên volume RDS 20 GB. Nếu bảng lớn ngoài dự kiến thì đã có sẵn `idx_user_memory_updated_at`
phục vụ batch cleanup `DELETE ... WHERE updated_at < NOW() - INTERVAL '1 year'`.
