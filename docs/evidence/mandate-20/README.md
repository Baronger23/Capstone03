# Mandate 20 Evidence Index

Evidence index cho Mandate #20 Backup/Restore DR.

## File Cần Đọc Trước

| Loại | File | Vai trò |
|---|---|---|
| Final evidence | `mandate-20-final-rds-pitr-evidence-20260729.md` | Bằng chứng cuối của RDS PITR drill: GOOD -> CORRUPTED -> restored GOOD, RPO pass, RTO 23.83 phút, link 4 video |
| Supporting evidence | `supporting-production-baseline-20260729.md` | Baseline production thật cho các data-tier/state trước drill |
| Supporting evidence | `supporting-rds-pitr-preflight-20260729.md` | Preflight RDS/PITR read-only trước drill |
| Supporting evidence | `supporting-scope-gap-analysis.md` | Matrix đối chiếu directive với scope đã claim, limitation, và phần cần accepted risk |
| Template | `production-baseline-template.md` | Mẫu trống cho lần baseline sau; không phải evidence của drill 2026-07-29 |

## Design / Runbook

| File | Vai trò |
|---|---|
| `docs/adr/0016-mandate-20-backup-restore-drill-cdo02.md` | ADR RPO/RTO, backup strategy/cadence, retention, delete-authority posture, restore drill approach |
| `docs/runbooks/mandate-20-rds-pitr-drill.md` | Runbook chạy RDS PITR drill an toàn, restore sang DB tách biệt |
| `docs/docx_cdo02/mandate-20-rds-pitr-restore-solution.md` | Solution note cho CDO02/mentor review |

## Current Status

```text
CDO02 design/ADR: ready
RDS PITR drill evidence: completed, Drive links recorded
RDS RPO target <= 5 minutes: PASS for drill marker
RDS RTO target <= 45 minutes: PASS, measured 23.83 minutes
Backup delete-permission verdict: pending enforcement evidence or accepted-risk note
Mandate #20 overall: RDS drill passed; overall Done still depends on accepted scope/limitations for non-RDS stores and delete-authority posture
```

## Không Nằm Trong PR Evidence

Video-capture script cá nhân được để ở `incident_report/mandate20-video-script-rds-pitr-drill-2026-07-29.md` để operator đọc/quay lại nếu cần. File đó không được push vào PR evidence vì nó là script vận hành cá nhân, không phải bằng chứng cuối.

## Required evidence fields

Each drill record must include:

```text
Git baseline:
AWS caller/account/region:
RDS source inventory:
T_good_commit:
T_restore:
T_corrupt_commit:
DB drill identifier:
Drill marker id:
Restore start/end:
RTO measured:
Production corrupt query:
Restored DB GOOD query:
Cleanup result:
Witness mode: mentor/PM live hoặc recorded video
```

## Coverage matrix status

| Store / state | RPO/RTO status | Backup/retention status | Evidence |
|---|---|---|---|
| RDS PostgreSQL | Target set: RPO <= 5 phút, RTO <= 45 phút; RPO passed with 0 row data loss; measured RTO 23.83 phút | Automated backup/PITR 7 ngày, RDS PITR drill passed | `mandate-20-final-rds-pitr-evidence-20260729.md` |
| ElastiCache Valkey | Pending final target or accepted cart-state limitation | Snapshot retention observed as 3 ngày, needs verdict | Snapshot/restore evidence or accepted cart-state strategy |
| MSK Kafka | Pending replay/reconciliation target; do not call PITR | Retention/replay strategy needs capture | Retention/replay or order reconciliation explanation |
| DynamoDB lock | Pending exclusion/verdict | Exclude if Terraform lock only | Exclusion reason |
| EBS legacy | Pending M8/M18 decision | Do not use as M20 proof unless ownership is clarified | Pending/accepted limitation |
| GitOps/IaC state | Pending state restore target if claimed | Git/state/versioning/Object Lock evidence if claimed | Commit/state/backend evidence |
| IAM/KMS/delete permission | Pending enforcement or accepted risk | Delete authority matrix needs review/accepted risk | Security verdict or recorded accepted-risk note required |

## Current Recommendation

Sau drill 2026-07-29, CDO02 nên:

- Dùng `mandate-20-final-rds-pitr-evidence-20260729.md` làm file evidence cuối khi gửi mentor/client.
- Dùng các file `supporting-*` để giải thích baseline, preflight, scope và limitation.
- Cleanup drill DB tạm sau khi mentor/PM xác nhận đã lưu đủ evidence.
- Chốt accepted-risk hoặc policy evidence cho phần backup delete-authority trước khi claim Mandate 20 full Done.

Lý do: Mandate 20 chấm trên toàn bộ tầng dữ liệu và trạng thái cụm/hạ tầng, không chỉ riêng RDS PITR drill.
