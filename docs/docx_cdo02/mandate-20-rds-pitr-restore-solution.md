# Solution Mandate #20 - Backup/Restore drill chứng minh khôi phục được

Kết luận ngay: **RDS hiện đã có nền tảng backup/PITR ổn để làm drill**, nhưng chưa đủ bằng chứng để nộp Mandate #20 nếu chưa thực hiện một lần restore drill thật trước mentor. Điểm thiếu không phải là "chưa bật backup"; điểm thiếu là chưa có ADR riêng ghi RPO/RTO và chưa có evidence: gây hỏng dữ liệu có kiểm soát -> restore vào môi trường tách biệt -> đối chiếu dữ liệu -> đo RTO thực.

Tài liệu này không chỉnh sửa hạ tầng và không phá production. Đây là đánh giá hiện trạng + runbook thao tác an toàn để chạy khi có mentor.

Điểm cần nói rõ: Mandate #20 cần tạo **một DB instance restore tạm/tách biệt** để chứng minh khôi phục, ví dụ `techx-tf3-postgres-drill-20260727-001`. Đây không phải DB production mới, không phải DB để app dùng lâu dài, và tuyệt đối không repoint traffic production sang DB này. DB drill chỉ tồn tại trong cửa sổ nghiệm thu để query đối chiếu dữ liệu rồi cleanup sau khi mentor chấp nhận evidence.

Phạm vi solution này: **chỉ làm RDS PITR restore drill**. Các phần datastore khác đã thuộc hồ sơ/chuyển đổi riêng, không lặp lại trong tài liệu này. Không dùng tài liệu này để claim thay cho phần đó.

## 1. Scope thực hiện

Store được chọn để chứng minh Mandate #20 trong solution này:

| Store | Vai trò | Hiện trạng trong repo | Kết luận Mandate #20 |
|---|---|---|---|
| RDS PostgreSQL `techx-tf3-postgres` | `catalog`/`reviews` đọc, `accounting` ghi đơn hàng | RDS hiện có backup/PITR, encryption, private endpoint, deletion protection | Store tốt nhất để làm PITR drill thật; vẫn phải restore thật để đạt M20 |

Bằng chứng repo chính:

- RDS: `storage_encrypted = true`, `manage_master_user_password = true`, `publicly_accessible = false`, `backup_retention_period = 7`, `deletion_protection = true`, `skip_final_snapshot = false` trong `infra/modules/datastores/rds.tf`.
- M20 không được claim hoàn tất nếu chưa có restore drill thật và evidence RTO.

## 2. Restore drill chính: RDS PITR

Chọn RDS làm drill trung tâm vì nó đáp ứng đúng yêu cầu "point-in-time restore về mốc trước sự cố" và có thể kiểm chứng bằng SQL mà không đổi app production.

Mục tiêu RDS trong ADR: **RPO <= 5 phút**, **RTO <= 45 phút**. Cơ sở là RDS automated backup 7 ngày + PITR; M20 phải chứng minh bằng restore-to-point-in-time vào DB instance mới.

So sánh ngắn để giải thích với mentor vì sao solution này chọn RDS làm drill:

| Store | Vì sao không chọn làm drill chính trong solution này |
|---|---|
| RDS PostgreSQL | Chọn làm drill chính vì có PITR native, restore được về đúng mốc trước sự cố vào DB instance tách biệt, kiểm chứng bằng SQL rõ ràng. |
| ElastiCache Valkey | Snapshot Valkey không phải PITR theo từng giây như RDS. Restore được, nhưng phải tạo replication group tạm và chỉ chứng minh snapshot restore, không mạnh bằng RDS PITR proof. |
| MSK Kafka | MSK không có restore-to-point-in-time kiểu RDS. Cơ chế phù hợp hơn là retention/replay consumer, không phải restore snapshot về thời điểm T. |
| Terraform/GitOps state | Có thể kiểm bằng S3 versioning/temp workspace, nhưng không nên ghi đè backend production trong drill này. |
| DynamoDB lock table | Lock table không nằm trên đường dữ liệu khách hàng; nếu mất có thể rebuild. Không dùng làm proof chính. |
| EBS/PVC legacy | Không dùng làm proof chính trong solution này; không delete/detach/restart volume hay workload stateful trong drill để tránh rủi ro production. |

Có cần tạo DB mới không: **Có, nhưng chỉ là DB instance restore tạm cho drill**. Không tạo DB production thay thế, không đổi connection string của service, không chuyển app sang DB drill. Lý do bắt buộc là mandate yêu cầu restore vào môi trường tách biệt và không được đè lên production.

Có sửa code không: **Không sửa code ứng dụng** để chạy RDS drill. Drill chỉ cần SQL probe trong schema riêng `dr_drill`, Terraform/AWS CLI tạo RDS restored instance tạm, và tài liệu/evidence. Không rebuild image, không đổi Helm values của app, không đổi ExternalSecret production.

Có cần tạo hạ tầng mới không: **Có, tạo hạ tầng tạm rồi tắt/xóa sau drill**:

| Hạ tầng tạm | Mục đích | Tạo bằng | Cleanup |
|---|---|---|---|
| RDS instance `techx-tf3-postgres-drill-YYYYMMDD-HHMM` | Môi trường restore tách biệt để query proof | Terraform additive-only nếu mentor yêu cầu IaC; nếu không thì AWS CLI/console | Terraform destroy target hoặc `aws rds delete-db-instance --skip-final-snapshot` sau khi mentor chấp nhận evidence |
| Security group/subnet override cho DB drill | Chỉ cần nếu restored DB không dùng được SG/subnet private hiện có | Ưu tiên reuse DB subnet group và SG hiện tại; chỉ tạo SG tạm nếu bắt buộc | Xóa SG tạm sau khi DB drill đã deleted |
| Debug pod hoặc SSM tunnel | Kết nối query DB drill | Dùng đường vận hành hiện có; không expose public | Xóa pod/tắt session sau drill |

Không tạo hạ tầng tạm ngoài RDS drill instance. Không tạo DB production mới.

Nguyên tắc an toàn:

- Chỉ tạo/corrupt dữ liệu probe riêng trong schema `dr_drill`; không động vào bảng khách hàng.
- Restore sang DB mới tên `techx-tf3-postgres-drill-YYYYMMDD-HHMM`, không repoint app.
- Kết nối restored DB qua SSM/bastion hoặc debug pod riêng; không sửa secret production.
- Đo RTO từ lúc bấm restore đến lúc query dữ liệu restored thành công.
- Sau khi mentor chấp nhận evidence mới cleanup DB drill theo quy trình riêng.

Cleanup sau nghiệm thu:

```powershell
# Nếu tạo bằng AWS CLI/console:
aws rds delete-db-instance `
  --db-instance-identifier techx-tf3-postgres-drill-20260727-001 `
  --skip-final-snapshot

aws rds wait db-instance-deleted `
  --db-instance-identifier techx-tf3-postgres-drill-20260727-001

# Nếu tạo bằng Terraform:
terraform destroy `
  -target='aws_db_instance.m20_rds_pitr_drill[0]' `
  -var="enable_m20_rds_drill=true" `
  -var="m20_drill_identifier=techx-tf3-postgres-drill-20260727-001" `
  -var="m20_restore_time=2026-07-27T03:15:00Z" `
  -var="m20_db_subnet_group_name=<private-db-subnet-group>" `
  -var='m20_vpc_security_group_ids=["sg-xxxxxxxx"]'
```

Chỉ cleanup sau khi đã lưu evidence. Không cleanup nếu mentor còn cần xem console hoặc query lại.

Runbook tóm tắt:

```powershell
# 0) Inventory, chỉ đọc
aws rds describe-db-instances `
  --db-instance-identifier techx-tf3-postgres `
  --query "DBInstances[0].{BackupRetention:BackupRetentionPeriod,LatestRestorableTime:LatestRestorableTime,DeletionProtection:DeletionProtection,Encrypted:StorageEncrypted,Public:PubliclyAccessible}"

# 1) Tạo probe trên production RDS, chỉ trong schema riêng
# Chạy qua psql tunnel tới techx-tf3-postgres:
CREATE SCHEMA IF NOT EXISTS dr_drill;
CREATE TABLE IF NOT EXISTS dr_drill.restore_probe (
  id text PRIMARY KEY,
  expected_payload text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO dr_drill.restore_probe(id, expected_payload)
VALUES ('m20-20260727-001', 'GOOD_BEFORE_CORRUPTION')
ON CONFLICT (id) DO UPDATE SET expected_payload = EXCLUDED.expected_payload, created_at = clock_timestamp();
SELECT clock_timestamp() AT TIME ZONE 'UTC' AS good_time_utc;

# 2) Đợi 60-120 giây, rồi gây hỏng có kiểm soát trong schema probe
UPDATE dr_drill.restore_probe
SET expected_payload = 'CORRUPTED_AFTER_GOOD_TIME'
WHERE id = 'm20-20260727-001';
SELECT id, expected_payload, clock_timestamp() AT TIME ZONE 'UTC' AS corrupt_time_utc
FROM dr_drill.restore_probe
WHERE id = 'm20-20260727-001';

# 3) Đợi LatestRestorableTime >= good_time_utc, bắt đầu đo RTO
$start = Get-Date
```

Nếu mentor yêu cầu tạo DB drill bằng IaC, thay bước tạo DB thủ công bằng Terraform additive-only. File IaC đề xuất:

- `infra/live/production/m20-rds-pitr-drill.tf`
- `infra/live/production/m20-rds-pitr-drill-variables.tf`

Skeleton Terraform:

```hcl
variable "enable_m20_rds_drill" {
  type    = bool
  default = false
}

variable "m20_drill_identifier" {
  type    = string
  default = "techx-tf3-postgres-drill-20260727-001"
}

variable "m20_restore_time" {
  type        = string
  default     = null
  description = "UTC restore time, for example 2026-07-27T03:15:00Z"
}

variable "m20_source_db_identifier" {
  type    = string
  default = "techx-tf3-postgres"
}

variable "m20_db_subnet_group_name" {
  type        = string
  default     = null
  description = "Private DB subnet group to use for the drill restore."
}

variable "m20_vpc_security_group_ids" {
  type        = list(string)
  default     = []
  description = "Existing private RDS security group ids allowed from the operator path."
}

resource "aws_db_instance" "m20_rds_pitr_drill" {
  count = var.enable_m20_rds_drill ? 1 : 0

  identifier          = var.m20_drill_identifier
  instance_class      = "db.t4g.micro"
  publicly_accessible = false

  db_subnet_group_name   = var.m20_db_subnet_group_name
  vpc_security_group_ids = var.m20_vpc_security_group_ids

  restore_to_point_in_time {
    source_db_instance_identifier = var.m20_source_db_identifier
    restore_time                  = var.m20_restore_time
  }

  deletion_protection = false
  skip_final_snapshot = true

  tags = {
    Mandate = "20"
    Purpose = "temporary-rds-pitr-drill"
  }
}
```

Apply chỉ được chạy nếu plan chỉ tạo thêm DB drill instance:

```powershell
terraform plan `
  -var="enable_m20_rds_drill=true" `
  -var="m20_drill_identifier=techx-tf3-postgres-drill-20260727-001" `
  -var="m20_restore_time=2026-07-27T03:15:00Z" `
  -var="m20_db_subnet_group_name=<private-db-subnet-group>" `
  -var='m20_vpc_security_group_ids=["sg-xxxxxxxx"]'

terraform apply `
  -var="enable_m20_rds_drill=true" `
  -var="m20_drill_identifier=techx-tf3-postgres-drill-20260727-001" `
  -var="m20_restore_time=2026-07-27T03:15:00Z" `
  -var="m20_db_subnet_group_name=<private-db-subnet-group>" `
  -var='m20_vpc_security_group_ids=["sg-xxxxxxxx"]'
```

Nếu không dùng IaC cho drill một lần, dùng AWS CLI:

```powershell
aws rds restore-db-instance-to-point-in-time `
  --source-db-instance-identifier techx-tf3-postgres `
  --target-db-instance-identifier techx-tf3-postgres-drill-20260727-001 `
  --restore-time "2026-07-27Txx:xx:xxZ" `
  --db-instance-class db.t4g.micro `
  --no-publicly-accessible

aws rds wait db-instance-available `
  --db-instance-identifier techx-tf3-postgres-drill-20260727-001
```

```sql
-- 4) Kết nối restored DB, verify probe đã quay về GOOD
SELECT id, expected_payload
FROM dr_drill.restore_probe
WHERE id = 'm20-20260727-001';
```

```powershell
$end = Get-Date
($end - $start).TotalMinutes
```

Tiêu chí pass:

- Production sau bước 2 hiện `CORRUPTED_AFTER_GOOD_TIME`.
- Restored DB tại point-in-time hiện `GOOD_BEFORE_CORRUPTION`.
- Restored DB nằm ở instance mới, không phải DB production.
- RTO thực <= 45 phút.
- Evidence lưu: output `describe-db-instances`, thời điểm good/corrupt, restore command, wait duration, SQL result trên restored DB, endpoint/identifier của DB drill.

## 3. Phần mentor xem console

Cần chuẩn bị các màn hình/lệnh chỉ đọc cho đúng store đang làm drill: RDS.

```powershell
# RDS automated backup/PITR
aws rds describe-db-instances --db-instance-identifier techx-tf3-postgres
aws rds describe-db-snapshots --db-instance-identifier techx-tf3-postgres
```

## 4. Backup safety và tách quyền

Ràng buộc thực tế của account: mentor đã chấp nhận **không dùng SCP** cho bài này, và account hiện có nhiều principal quyền admin. Vì vậy không được claim rằng hệ thống đã chặn tuyệt đối việc xóa backup/ransomware. Những phần bên dưới chỉ là guard ở mức IAM/quy trình/repo có thể bổ sung; trong account hiện tại, admin vẫn có thể bypass.

Hiện tại có:

- RDS deletion protection và final snapshot.
- Secrets trong Secrets Manager/External Secrets; RDS password do RDS quản lý.
- KMS key rotation cho datastores.
- Audit layer có S3 Object Lock/prevent_destroy cho CloudTrail, nhưng đây là audit archive, không phải backup vault của data store.

Gap cần ghi thẳng trong ADR:

- Chưa thấy IAM/quy trình riêng chống xóa RDS snapshot/automated backup.
- Chưa thấy explicit deny cho các action như `rds:DeleteDBSnapshot`, `rds:DeleteDBInstanceAutomatedBackup`, `rds:DeleteDBInstance`, `kms:ScheduleKeyDeletion` áp dụng bắt buộc cho operator thường.

Quyền xóa backup nên ghi:

| Nhóm | Được xóa backup? | Ghi chú |
|---|---|---|
| `tf3-production-readonly` | Không | Chỉ đọc/xem evidence |
| `tf3-production-operator` | Không theo thiết kế mong muốn | Hiện vẫn phải kiểm quyền thực tế vì account có admin rộng |
| CI Terraform | Không được xóa backup trực tiếp ngoài PR được review | Chỉ enforce ở mức IAM/quy trình hiện có; không claim chặn tuyệt đối admin |
| Backup custodian/break-glass | Có, có điều kiện | Cần MFA, ticket, mentor/owner approval, CloudTrail alert |

Phần có thể thêm vào repo nhưng chưa claim là đã chặn được:

- ADR ghi rõ ai được xóa backup.
- Terraform/IAM policy mẫu deny destructive backup actions cho operator role.
- Test hoặc checklist `aws iam simulate-principal-policy` cho operator role.
- Backlog/security note: account có nhiều admin nên guard IAM/quy trình không chặn tuyệt đối được mọi người.

## 4.1. Phần bàn giao cho CDO01 Security

Phạm vi của **CDO02** trong solution này là Reliability/Operational Excellence: RDS PITR restore drill, đo RTO, chứng minh dữ liệu quay lại đúng, và viết ADR/evidence vận hành. Các mục dưới đây thuộc phần Security do **CDO01** phụ trách xác nhận hoặc triển khai riêng; CDO02 không tự ý sửa trong drill để tránh phát sinh rủi ro ngoài phạm vi.

| Hạng mục Security | Việc cần CDO01 làm | Lý do |
|---|---|---|
| Quyền xóa RDS backup/snapshot | Xác nhận ai được phép gọi `rds:DeleteDBSnapshot`, `rds:DeleteDBInstanceAutomatedBackup`, `rds:DeleteDBInstance` | M20 yêu cầu tách quyền để operator thường không xóa được backup |
| IAM guard cho operator | Nếu phù hợp, thêm deny policy/permission boundary cho operator role; không dùng SCP vì mentor đã chấp nhận không dùng SCP | Account có nhiều admin nên CDO không claim chặn tuyệt đối |
| Break-glass process | Ghi rõ principal nào được xóa backup trong trường hợp khẩn cấp, cần ticket/MFA/mentor-owner approval | Tránh vừa "ai cũng admin" vừa không có quy trình trách nhiệm |
| Evidence review | Security xem lại phần encryption at rest, private endpoint, Secrets Manager, KMS key rotation | CDO dùng làm input cho ADR nhưng không tự claim phần Security |

Deliverable CDO01 nên trả lại cho ADR M20:

- Danh sách role/user được phép xóa RDS backup/snapshot.
- Kết quả kiểm tra quyền operator không được xóa backup, hoặc ghi rõ accepted risk nếu chưa chặn được do admin rộng.
- Xác nhận không dùng SCP là quyết định đã được mentor chấp nhận.

## 5. ADR cần nộp

Tạo/sửa các file sau, không cần sửa code ứng dụng:

| File | Loại thay đổi | Mục đích |
|---|---|---|
| `docs/docx_cdo02/mandate-20-rds-pitr-restore-solution.md` | Đã tạo | Bản phân tích và phương án để review trước |
| `docs/adr/0013-mandate-20-backup-restore-drill.md` | Cần thêm | ADR ký tên: RPO/RTO, strategy, quyền xóa backup, runbook drill |
| `docs/runbooks/mandate-20-rds-pitr-drill.md` | Nên thêm | Runbook thao tác chi tiết từng lệnh cho mentor session |
| `docs/evidence/mandate-20/README.md` | Cần thêm sau drill | Index evidence: thời điểm drill, RTO, link output |
| `docs/evidence/mandate-20/rds-pitr-drill-YYYYMMDD.md` | Cần thêm sau drill | Biên bản kết quả restore thật |
| `infra/live/production/m20-rds-pitr-drill.tf` | Optional, chỉ nếu mentor yêu cầu IaC | Tạo thêm RDS drill instance tạm, mặc định tắt |
| `infra/live/production/m20-rds-pitr-drill-variables.tf` | Optional, chỉ nếu mentor yêu cầu IaC | Biến bật/tắt drill, restore time, identifier, subnet group, SG |

ADR mới, ví dụ `docs/adr/0013-mandate-20-backup-restore-drill.md`, cần có nội dung tối thiểu:

- Phạm vi drill: RDS PostgreSQL `techx-tf3-postgres`.
- RPO/RTO RDS: RPO <= 5 phút, RTO <= 45 phút.
- Backup cadence/retention: RDS automated backup 7 ngày + PITR.
- Ai được xóa backup và IAM/quy trình guard mong muốn; ghi rõ mentor đã chấp nhận không dùng SCP.
- Runbook RDS PITR drill, evidence checklist, cleanup checklist.
- Kết quả drill thực tế: start/end, RTO phút, restore target, SQL proof, người chứng kiến.

## 5.1. Cách làm để tránh downtime hoặc sập hạ tầng

Các nguyên tắc bắt buộc trong buổi drill:

- Không đổi `DB_CONNECTION_STRING` của production.
- Không sync ArgoCD thay đổi app trong lúc drill, trừ khi đó là PR tài liệu/evidence không ảnh hưởng runtime.
- Không scale down/up production workload để tạo sự cố.
- Không chạy `DROP`, `DELETE`, `TRUNCATE`, `UPDATE` trên bảng khách hàng. Chỉ thao tác trong schema probe `dr_drill`.
- Không restore đè lên RDS production. Chỉ restore sang identifier mới `techx-tf3-postgres-drill-*`.
- Không xóa RDS drill instance cho đến khi mentor xác nhận evidence đủ.
- Trước khi chạy restore, chụp lại output inventory RDS để có baseline.
- Nếu `restore-db-instance-to-point-in-time` trả lỗi hoặc DB drill tạo không lên, dừng drill và không cố patch production để "cứu".

Các bước thực hiện an toàn:

1. Read-only inventory: RDS backup/PITR.
2. Tạo schema/bảng probe `dr_drill.restore_probe` trên RDS production.
3. Ghi giá trị GOOD và ghi lại `good_time_utc`.
4. Gây hỏng có kiểm soát chỉ bằng cách update chính row probe sang `CORRUPTED_AFTER_GOOD_TIME`.
5. Restore RDS về `good_time_utc` sang DB instance tạm.
6. Query DB restored, chứng minh row probe là `GOOD_BEFORE_CORRUPTION`.
7. Đo RTO.
8. Lưu evidence.
9. Cleanup DB drill sau khi mentor duyệt.

## 6. Đánh giá pass/fail trước khi nộp

| Yêu cầu Mandate #20 | Hiện trạng | Đánh giá |
|---|---|---|
| Phạm vi drill RDS rõ ràng | RDS đã nhận diện và có PITR | Đạt về thiết kế, chờ drill thật |
| RPO/RTO rõ ràng, cadence tương xứng | Chưa thấy ADR #20 | Chưa đạt |
| Point-in-time restore | RDS có PITR | Chưa đạt đến khi restore DB drill thật |
| Tested restore drill | Chưa thấy evidence mandate #20 | Chưa đạt |
| Backup an toàn, mã hóa, tách quyền xóa | Encryption tốt; deletion protection có; tách quyền xóa backup chưa rõ | Đạt một phần |

Kết luận nộp mentor: có nền tảng để đạt nhanh bằng RDS PITR drill, nhưng không nên claim Mandate #20 đã hoàn thành cho đến khi chạy restore thật và lưu evidence. Việc cần làm tiếp là ADR + RDS restore drill + IAM backup-delete guard nhỏ.
