# PM-127 — Acceptance matrix

**Cập nhật:** 2026-07-28
**Directive #10** — Secure delivery pipeline

Cột *Bằng chứng* ghi thứ tự chạy lại được, không phải khẳng định suông.

---

## A. Definition of Done (Jira PM-127)

| # | DoD | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | Mọi image tự build có SBOM, tra được theo digest **bằng 1 lệnh** | ✅ | `scripts/ci/get-sbom.sh <digest> --platform linux/amd64 --metadata` → CycloneDX, components > 0. **21/21** digest first-party. Wrapper tự chặn cosign sai version |
| 2 | `kubectl get clusterpolicy` cho **cả 2 policy**: `Enforce/Ready=True` | 🟡 1/2 | `allow-approved-external-image-digests` = **`Enforce/True`** (live). `verify-first-party-signatures` = merged (#540), **chờ sync** |
| 3 | Deploy image chưa ký / sai identity → **bị từ chối**, message rõ | ⏳ | 7 fixture sẵn ở `admission-tests/`. Chạy sau khi sync 7B |
| 4 | **0 false-positive** trên PolicyReport cho image hợp lệ đang chạy sống | ✅ | 40 pod: first-party **30 pass / 0 fail**; external **0 bị chặn**. Vi phạm còn lại đều là **true positive trên resource đã chết** |

---

## B. Yêu cầu Directive #10

| # | Yêu cầu | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | PR với CI đỏ → **chặn merge** | ✅ | PM-126: branch protection require `Secure delivery gate`, `required_approvals: 1`. PR #350/#351 bị `BLOCKED` thật |
| 2 | Deploy image chưa ký → **admission từ chối** | 🟡 | 7A live; 7B chờ sync + chạy test |
| 3 | Chỉ vào pod đang chạy → **truy ngược full provenance** | ✅ | `provenance-walkthrough.md` — chuỗi đầy đủ cho pod `quote` |
| — | SBOM + provenance, ký cosign | ✅ | 21/21 digest có chữ ký keyless + CycloneDX 2 platform |
| — | Reference theo **digest**, cấm floating tag | ✅ | drift check `exit 0`: **11/11** external pin digest, khớp catalog từng ký tự |
| — | Actions pin commit SHA, base image pin digest | ✅ | `Immutable dependency pins` check pass mọi PR |
| — | Scan CVE/IaC/secret/SAST là **cổng chặn** | ✅ | Trivy pre-push + post-push; `Secure delivery gate` là required check |

---

## C. Chuỗi provenance (yêu cầu #3)

```
pod quote-79b77dd947-n6mrq
  └─ digest  sha256:5035d768…          imageID = spec.image, không qua tag
     └─ commit  947146d8…              lấy từ SBOM đã ký, không tra ngoài
        └─ PR #502  reviewer ThuyTrang9525
           └─ run 30334711133          Trivy pre-push + post-push pass
              └─ signer  build-push-ecr.yml@refs/heads/main   keyless
                 └─ SBOM  CycloneDX, 95 component, amd64 + arm64
```

Chi tiết + lệnh từng bước: [`provenance-walkthrough.md`](provenance-walkthrough.md)

---

## D. Phạm vi đã phủ

| Nhóm | Số lượng | Trạng thái |
|---|---|---|
| Digest first-party (chữ ký + SBOM) | **21** | ✅ verify bằng cosign v2.6.2, 0 fail |
| External pin digest + trong catalog | **11** | ✅ khớp chính xác từng ký tự |
| Image AIO02 (`tf-2-ai-engine` ×2, `shopping-copilot`) | **3** | ✅ pin digest + vào catalog (#529) |
| Pod đang chạy trong `techx-tf3` | **40** | ✅ không cái nào bị chặn |

---

## E. Non-regression (dưới 7A Enforce)

| Kiểm tra | Kết quả |
|---|---|
| Pod đang chạy | **40**, không có pod nào ngoài `Running`/`Completed` |
| Storefront (`frontend-proxy`) | 2/2 `Running` |
| `flagd` | `2/2 Running` — cơ chế đọc flag **không đổi** |
| Admission denial do policy | **0** |

---

## F. Những chỗ suýt kết luận sai — ghi lại để khỏi lặp

| Vấn đề | Vì sao nguy hiểm | Đã xử |
|---|---|---|
| **Cosign v3 báo SBOM missing** | Digest cũ còn OCI 1.1 referrers từ pipeline trước; v3 đọc referrers, thấy chữ ký cũ, kết luận thiếu CycloneDX — **false negative trông như bằng chứng hỏng** | `get-sbom.sh` chặn sai major version kèm hướng dẫn |
| **SBOM backfill ghi sai commit** | Bản đầu ghi commit **lúc backfill**, không phải commit build → truy vết dẫn tới commit không liên quan, hỏng đúng yêu cầu #3 | PR #498: truyền SHA gốc theo từng cặp, truy lại từ commit promotion |
| **Đọc PolicyReport ngay sau rollout** | Kyverno `backgroundScanInterval=1h` → thấy "fail" của lần scan cũ | Luôn đối chiếu bằng đánh giá tay trên pod sống |
| **Đếm số fail thô của report** | Gộp cả ReplicaSet đã chết → 46 fail trong khi runtime chỉ có 20 vấn đề | Chỉ đo trên pod `Running` |
| **Dùng danh sách `.sig` cache** | Snapshot lạc hậu (29 vs 31) → báo nhầm 2 ReplicaSet sống là chưa ký, suýt chặn 7B | Verify trực tiếp bằng cosign |
| **Digest đã ghi `.att` không sửa lại được** | ECR immutable chỉ cho ghi 1 lần/subject → `quote` phải **rebuild**, không vá được | Pre-flight từ chối cả lô nếu digest đã có `.att` |

---

## G. Còn lại

| Việc | Ai làm |
|---|---|
| Sync `kyverno-policies` (1 ClusterPolicy, `prune=False`) → 7B live | Người có quyền ghi |
| Chạy 7 case trong `admission-tests/` **trong `techx-tf3`** | Người có quyền tạo pod |
| Merge #539 (provenance walkthrough) | — |

Role `tf3-production-readonly` không patch được Application lẫn tạo pod, nên hai việc đầu phải người khác thực hiện.

---

## H. Rủi ro đã biết, chấp nhận có chủ đích

**`kubectl rollout undo` sẽ bị chặn** — 79/266 ReplicaSet đã chết còn tham chiếu digest chưa ký. Không cái nào đang tạo pod.

Đường rollback được hỗ trợ là **`git revert` + ArgoCD**, deploy lại digest từ `values-prod.yaml` — toàn bộ đã ký, **không bị ảnh hưởng**.

Một revision cũ không chứng minh được nguồn gốc thì đúng ra không nên quay lại được.

**`kubectl debug` bị chặn** với image ngoài catalog. Có chủ đích — chính cơ chế này bắt được 3 container `nicolaka/netshoot` bỏ quên trên pod `fraud-detection`. Ai cần troubleshoot thì dùng image trong catalog hoặc thêm qua PR (CI drift gate kiểm).

**Gợi ý ngoài phạm vi:** 266 ReplicaSet là quá nhiều, nên đặt `revisionHistoryLimit`.
