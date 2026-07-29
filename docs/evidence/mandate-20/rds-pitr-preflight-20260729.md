# Mandate 20 evidence - RDS/PITR preflight before restore drill

**Date/time captured (UTC):** 2026-07-29T02:54:55Z  
**Scope:** read-only preflight before RDS PITR restore drill  
**Account:** `197826770971`  
**Region:** `ap-southeast-1`  
**AWS caller:** `arn:aws:iam::197826770971:user/cdo-2-admin-team`  
**Git baseline:** `origin/main` = `8d346c4fa8ab652cebe35ad47e12cdd0c31eeda6`

## Summary verdict

```text
RDS source status: available
Backup retention: 7 days
Latest restorable time: 2026-07-29T02:50:54Z
Storage encrypted: true
Deletion protection: true
Publicly accessible: false
Multi-AZ: true
Existing drill/restore DB instances: none found
Preflight result: ready to schedule controlled PITR restore drill
```

This file is **pre-drill evidence only**. It proves that the RDS/PITR baseline is suitable for a restore drill, but it does not by itself prove Mandate 20 completion. Mandate 20 still requires the controlled GOOD -> CORRUPTED -> RESTORED GOOD drill, measured RTO, mentor/PM witness, and backup delete-permission verdict.

## AWS caller

Command:

```powershell
aws sts get-caller-identity --output json
```

Output:

```json
{
  "UserId": "AIDAS4D3E7ANWXCYOWPQJ",
  "Account": "197826770971",
  "Arn": "arn:aws:iam::197826770971:user/cdo-2-admin-team"
}
```

## RDS source inventory

Command:

```powershell
aws rds describe-db-instances `
  --region ap-southeast-1 `
  --db-instance-identifier techx-tf3-postgres `
  --query "DBInstances[0].{Id:DBInstanceIdentifier,Status:DBInstanceStatus,Engine:Engine,EngineVersion:EngineVersion,Encrypted:StorageEncrypted,Kms:KmsKeyId,BackupRetention:BackupRetentionPeriod,LatestRestorable:LatestRestorableTime,DeletionProtection:DeletionProtection,MultiAZ:MultiAZ,AZ:AvailabilityZone,Public:PubliclyAccessible,SubnetGroup:DBSubnetGroup.DBSubnetGroupName,VpcSGs:VpcSecurityGroups[].VpcSecurityGroupId,InstanceClass:DBInstanceClass,AllocatedStorage:AllocatedStorage,StorageType:StorageType}" `
  --output json
```

Output:

```json
{
  "Id": "techx-tf3-postgres",
  "Status": "available",
  "Engine": "postgres",
  "EngineVersion": "17.9",
  "Encrypted": true,
  "Kms": "arn:aws:kms:ap-southeast-1:197826770971:key/3c6f7587-f647-4f96-a3ba-411d8880f1c9",
  "BackupRetention": 7,
  "LatestRestorable": "2026-07-29T02:50:54+00:00",
  "DeletionProtection": true,
  "MultiAZ": true,
  "AZ": "ap-southeast-1c",
  "Public": false,
  "SubnetGroup": "techx-tf3-postgres",
  "VpcSGs": [
    "sg-025478cd9d0ae1f52"
  ],
  "InstanceClass": "db.t4g.micro",
  "AllocatedStorage": 20,
  "StorageType": "gp3"
}
```

## Snapshot baseline

Command:

```powershell
aws rds describe-db-snapshots `
  --region ap-southeast-1 `
  --db-instance-identifier techx-tf3-postgres `
  --query "DBSnapshots[].{Id:DBSnapshotIdentifier,Type:SnapshotType,Status:Status,Encrypted:Encrypted,Kms:KmsKeyId,Created:SnapshotCreateTime,AllocatedStorage:AllocatedStorage}" `
  --output json
```

Observed snapshots:

| Snapshot id | Type | Status | Encrypted | Created UTC | Storage |
|---|---|---|---|---|---|
| `rds:techx-tf3-postgres-2026-07-21-15-39` | automated | available | true | 2026-07-21T15:39:55.773Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-21-20-07` | automated | available | true | 2026-07-21T20:07:10.899Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-22-20-07` | automated | available | true | 2026-07-22T20:07:10.979Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-23-20-07` | automated | available | true | 2026-07-23T20:07:11.860Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-24-20-07` | automated | available | true | 2026-07-24T20:07:10.093Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-25-20-07` | automated | available | true | 2026-07-25T20:07:16.730Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-26-20-07` | automated | available | true | 2026-07-26T20:07:08.901Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-27-20-07` | automated | available | true | 2026-07-27T20:07:08.099Z | 20 GiB |
| `rds:techx-tf3-postgres-2026-07-28-20-07` | automated | available | true | 2026-07-28T20:07:18.802Z | 20 GiB |
| `techx-tf3-postgres-pre-cleanup-20260721-2242` | manual | available | true | 2026-07-21T15:43:14.300Z | 20 GiB |

## Existing drill/restore DB check

Command:

```powershell
aws rds describe-db-instances `
  --region ap-southeast-1 `
  --query "DBInstances[?contains(DBInstanceIdentifier,'drill') || contains(DBInstanceIdentifier,'restore') || contains(DBInstanceIdentifier,'m20')].{Id:DBInstanceIdentifier,Status:DBInstanceStatus,Created:InstanceCreateTime,Public:PubliclyAccessible}" `
  --output json
```

Output:

```json
[]
```

No stale Mandate 20 drill/restore DB instance was found at preflight time.

## Preflight pass/fail checklist

| Check | Result | Evidence |
|---|---|---|
| Correct AWS account | Pass | Account `197826770971` |
| Correct region | Pass | `ap-southeast-1` |
| Source DB exists | Pass | `techx-tf3-postgres` |
| Source DB available | Pass | `Status = available` |
| Automated backup/PITR enabled | Pass | `BackupRetention = 7`, `LatestRestorable = 2026-07-29T02:50:54Z` |
| Encryption at rest | Pass | `Encrypted = true`, KMS key present |
| Deletion protection | Pass | `DeletionProtection = true` |
| Private endpoint posture | Pass | `Public = false`, private subnet group present |
| No stale drill DB | Pass | query returned `[]` |

## Next evidence to collect during drill

The next evidence record should capture:

- `DrillMarkerId`
- `T_good_commit_utc`
- `T_corrupt_commit_utc`
- selected `T_restore`
- RDS restore command output
- DB drill identifier and endpoint
- restore start/end timestamps
- measured RTO
- production marker query showing `CORRUPTED_AFTER_GOOD_TIME`
- restored DB marker query showing `GOOD_BEFORE_CORRUPTION`
- mentor/PM witness
- cleanup result after witness confirmation

