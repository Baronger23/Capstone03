# 11 — Tham chiếu rollback (chuẩn bị TRƯỚC khi merge bot PR-D)

## Trạng thái đang live (đọc từ origin/main trước rollout)

```
service : product-reviews
digest  : sha256:35f413f43f8840039383f4fe64440e7f06415c6e5fb70591480451ee84d54067
tag     : 177d7d1-30382089768-product-reviews
file    : phase3 - information/deploy/values-prod.yaml  (dòng 893-895)
commit  : 3624f53 chore(deploy): bump images from 177d7d1
```

**Đây là digest phải quay về khi rollback.** Đọc lại giá trị thực tế ngay trước rollout —
đừng tin con số trong tài liệu.

## Xác nhận cấu hình Argo không đổi

- Application `techx-corp`, `targetRevision: main`, 6 valueFiles đúng thứ tự.
- `product-reviews` nằm trong `ignoreDifferences` `/spec/replicas` (HPA sở hữu replicas).
- `syncPolicy.automated` + `prune` + `selfHeal` → merge PR-D là deploy trong ~3 phút.

## Cách rollback

1. Dừng ramp/load, báo on-call.
2. Mở PR rollback đã chuẩn bị từ head của PR-D, một commit duy nhất đưa
   `components.product-reviews.imageOverride.digest` về `sha256:35f413f4…`.
3. Merge qua review khẩn cấp trong `ROLLBACK_DECISION_DEADLINE_MIN`.
4. Để **ArgoCD** đồng bộ. KHÔNG `helm upgrade`, `kubectl set image`, patch Deployment
   hay `kubectl rollout undo` — `selfHeal` sẽ ghi đè và tạo drift so với `main`.
5. `kubectl -n techx-tf3 rollout status deployment/product-reviews --timeout=10m`
6. Verify lại read RPC + storefront.

## Schema khi rollback

**GIỮ bảng `reviews.product_summaries`.** Migration là additive; image cũ không đọc bảng
này nên nó vô hại. **Không drop table trong lúc incident.** Muốn dọn dữ liệu thì làm
change riêng sau khi đã backup và review.

## Còn phải điền trước khi GO

```
CHANGE_OWNER=
ON_CALL=
AIO_REVIEWER=
CDO_REVIEWER=
CHANGE_WINDOW=
ROLLBACK_BRANCH_OR_PR=
ROLLBACK_DECISION_DEADLINE_MIN=
RESTORE_OBJECTIVE_MIN=
BREAK_GLASS_OWNER=
```
