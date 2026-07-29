# G8 — Production preflight

**Kết luận: NO-GO cho bước rollout (merge bot PR-D). Migration (PR-C) KHÔNG bị chặn.**

## PASS

| Mục | Kết quả |
|---|---|
| ArgoCD `techx-corp` | `Synced` / `Healthy`, rev `0bf98e2` (= commit merge PR #590) |
| Sync sau khi merge PR-B | Argo đã sync code merge và **không rollout gì** — xác nhận thực tế PR-B thuần code |
| Deployment | 2/2 ready, 2/2 available, 0 restart |
| Digest đang chạy trên pod | `sha256:35f413f43f8840039383f4fe64440e7f06415c6e5fb70591480451ee84d54067` (khớp `values-prod.yaml` → tham chiếu rollback đúng) |
| HPA | min 2 / max 6, current 2, desired 2 |
| PDB | `minAvailable: 1`, `disruptionsAllowed: 1`, `currentHealthy: 2` |
| EndpointSlice | 2/2 endpoint ready |
| ExternalSecret | `postgres-connection` + `valkey-auth` = `True` / `SecretSynced` |
| IRSA | SA `product-reviews-bedrock` → `arn:aws:iam::197826770971:role/techx-corp-tf3-product-reviews-bedrock` |

## FAIL — không đủ chỗ cho pod surge

`product-reviews` tolerate **duy nhất** `techx.io/workload=elastic`:

```
tolerations: [{key: techx.io/workload, operator: Equal, value: elastic, effect: NoSchedule}]
nodeSelector: {techx.io/workload: elastic}
topologySpread: kubernetes.io/hostname       maxSkew=1 minDomains=2 DoNotSchedule
                topology.kubernetes.io/zone  maxSkew=1 minDomains=2 DoNotSchedule
                nodeTaintsPolicy = <unset>  ->  mặc định Ignore
```

4 node `elastic`, nhưng **2 node có thêm taint `techx.io/arch=arm64:NoSchedule`** (nodepool ARM
của CDO01, PR #588 `feat/arm-nodepool-foundation`):

| Node | Zone | Instance | `techx.io/arch` | product-reviews xếp được? | Đang chạy |
|---|---|---|---|---|---|
| `ip-10-0-16-235` | 1b | t3.medium | — | ✅ | 1 pod |
| `ip-10-0-36-118` | 1c | t3a.medium | — | ✅ | 1 pod |
| `ip-10-0-0-54` | 1a | c6g.large | `arm64` | ❌ untolerated | 0 |
| `ip-10-0-42-133` | 1c | m6gd.large | `arm64` | ❌ untolerated | 0 |

`nodeTaintsPolicy` không set → mặc định **`Ignore`**, nghĩa là node bị taint **vẫn được tính là
domain** khi tính skew, dù pod không xếp lên đó được. Thử từng chỗ đặt pod surge:

| Đặt surge ở | Phân bố host | Skew | Kết quả |
|---|---|---|---|
| `ip-10-0-16-235` | 2,1,0,0 | 2 | ❌ vượt `maxSkew=1` |
| `ip-10-0-36-118` | 1,2,0,0 | 2 | ❌ vượt `maxSkew=1` |
| `ip-10-0-0-54` | 1,1,1,0 | 1 | ❌ untolerated taint `arm64` |
| `ip-10-0-42-133` | 1,1,0,1 | 1 | ❌ untolerated taint `arm64` |

Ràng buộc **zone** độc lập cũng ép về đúng chỗ đó: hiện 1b=1, 1c=1, 1a=0; thêm vào 1b hoặc 1c →
skew 2 ❌; chỉ 1a hợp lệ — mà node `elastic` duy nhất ở 1a chính là node ARM bị taint.

→ Với `maxSurge: 1` + `maxUnavailable: 0`, pod surge **không có chỗ hợp lệ nào**. Rolling deploy sẽ
treo ở `Pending`. Không mất service (pod cũ vẫn chạy nhờ `maxUnavailable: 0`), nhưng change không
hoàn tất và Argo sẽ ở `Progressing`.

## Đây không phải lý thuyết — đã xảy ra với service khác trong 1 giờ qua

```
57m  FailedScheduling  frontend-proxy-54669f8fc8-mwcwf
     0/10 nodes are available: 2 node(s) didn't match pod topology spread constraints,
     4 node(s) didn't match Pod's node affinity/selector, 4 node(s) had untolerated taint(s)
49m  FailedScheduling  quote-595c7645cf-5sxwm
21m  FailedScheduling  product-catalog-7f948c89c5-7qrp7
```

Batch nodepool ARM của CDO01 **đang chạy dở** (node `ip-10-0-42-133` tạo lúc 06:08, tức 8 phút trước
khi đo). CLAUDE.md đã cảnh báo sẵn: *"CDO01 đang chạy dở batch Karpenter elastic — đừng đụng nodegroup
khi họ chưa xong"*. Điều kiện PASS của G8 "không có rollout/sync/incident khác đang chạy" **không đạt**.

## Migration (PR-C) KHÔNG bị chặn

Job migration `nodeSelector: elastic` + tolerate `techx.io/workload`, và **không có
topologySpreadConstraints**. Nó xếp được lên `ip-10-0-16-235` hoặc `ip-10-0-36-118`. Chạy migration
trước là an toàn và đúng thứ tự.

## Ghi chú: CLAUDE.md lạc hậu

CLAUDE.md yêu cầu `export AWS_PROFILE=techx-new`. **Profile đó không còn tồn tại.** Profile hiện có
đều trỏ đúng account `197826770971`: `default`/`nvtank-readonly` (role readonly, đủ cho preflight),
`tf3-member-base`, `acc-moi` (cdo-admin-team). Readonly không đọc được `secrets` — dùng trạng thái
`ExternalSecret` để verify thay thế.
