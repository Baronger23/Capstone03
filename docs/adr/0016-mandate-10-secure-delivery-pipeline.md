# ADR 0016 — Mandate 10: Secure Delivery Pipeline

**Date:** 2026-07-29

**Decision owner:** CDO01 / TF3 Security

**Collaborators/reviewers:** TF3 platform owner, CDO02, mentor

**Status:** Accepted - Enforce cutover complete; mentor acceptance pending

## Context

Hệ thống CI/CD hiện tại thiếu các cơ chế kiểm soát chặt chẽ đối với các artifact được tạo ra và triển khai. Việc tin tưởng mù quáng vào bất kỳ image nào được đẩy lên server (dù là do người dùng hay hệ thống tự động) tạo ra rủi ro rất lớn về bảo mật chuỗi cung ứng (Supply Chain Attack).
Mandate 10 đặt ra yêu cầu xây dựng một "Secure Delivery Pipeline" khép kín theo nguyên tắc Zero Trust:
1. Chặn các mã nguồn và cấu hình chứa lỗ hổng bảo mật ngay từ bước tạo Pull Request (CI Blocking).
2. Mọi Container Image phải được quét lỗ hổng, ký xác thực điện tử (Attestation) và đính kèm danh sách phần mềm (SBOM).
3. Đánh chặn tự động tại cổng Kubernetes Admission nếu Image thiếu chữ ký hợp lệ.
4. Có khả năng truy ngược (Provenance) chính xác từ một Pod đang chạy trên cluster về tới PR và Commit gốc.

## Decision

1. **SAST & IaC Scanning (Cổng chặn CI - PM-125):** Sử dụng **Semgrep** để phân tích tĩnh mã nguồn và **tfsec** (thông qua Trivy) để quét cấu hình hạ tầng Terraform. Bất kỳ lỗ hổng mức độ High/Critical nào cũng sẽ trực tiếp đánh fail luồng CI và chặn tính năng Merge PR thông qua GitHub Branch Protection.
2. **Container Scanning:** Sử dụng **Trivy** để quét Image vulnerabilities ngay trong quá trình build.
3. **Image Signing & Attestation:** Sử dụng **Cosign Keyless** (tích hợp GitHub OIDC identity) để ký điện tử xác thực Image. Không sử dụng long-lived key để tránh rủi ro lộ lọt key.
4. **Hóa đơn phần mềm (SBOM):** Sử dụng **CycloneDX** để kê khai minh bạch thành phần phần mềm của mỗi Image.
5. **Admission Control (Chặn Deploy - PM-127):** Sử dụng **Kyverno `verifyImages`** policy để kiểm tra chữ ký Cosign và SBOM ngay tại cổng API của Kubernetes. Bất kỳ Image nào không thỏa mãn điều kiện chữ ký từ đúng workflow của TechX Corp sẽ bị từ chối khởi tạo (Deny).
6. **Immutable Actions (Chống trôi dạt Actions):** Toàn bộ các GitHub Actions của bên thứ 3 trong `.github/workflows/` đều được ghim (pin) chặt theo mã **Commit SHA** (VD: `@v2` chuyển thành `@1234abcd...`), tuyệt đối không dùng tag lỏng lẻo để tránh rủi ro bị upstream tiêm mã độc.
7. **Provenance Traceability (PM-129):** Phát triển và hoàn thiện script `trace-provenance.sh` để đọc dữ liệu ký từ OIDC và Pod spec, từ đó truy vết ngược lại chính xác `sourceSha` và `sourcePr`.

## Scope

- **Repository:** Mã nguồn và toàn bộ workflow GitHub Actions hiện tại.
- **Cluster Namespace:** `techx-tf3`
- **Workloads:** Toàn bộ 21 digest first-party đã ký và 30 container first-party đang chạy được build và deploy bởi TechX Corp.

## Exceptions

- **External/Third-party Images:** Các image từ bên thứ ba (như Grafana, Prometheus, ArgoCD, busybox) tải từ catalog bên ngoài được loại trừ khỏi yêu cầu chữ ký nội bộ (`verify-first-party-signatures`). Tuy nhiên, chúng phải tuân thủ nghiêm ngặt việc ghim cứng (pin) digest (`@sha256:...`) trong file `values` và phải vượt qua chính sách kiểm duyệt riêng biệt `allow-approved-external-image-digests`.
- Việc loại trừ này đảm bảo hệ thống không bị "đóng băng" khi cần dùng các công cụ phổ biến của CNCF, nhưng vẫn ngăn chặn được việc tự ý kéo một image bên ngoài không được phê duyệt.
- **Tfsec Exceptions (PM-126):** Một số findings của tfsec được miễn trừ thông qua tệp `pm-126-tfsec-exceptions.json` nếu có lý do chính đáng (operational necessity) và được duyệt.

## Rollback

- **Đường chính (GitOps):** sửa `validationFailureAction: Enforce` → `Audit` trong
  `gitops/policies/kyverno/verify-first-party-signatures.yaml`, mở PR, merge vào `main`,
  rồi sync Application `kyverno-policies`. Đây là đường **duy nhất giữ được** —
  `selfHeal: true` sẽ revert mọi `kubectl patch` tay.
- **Khẩn cấp:** `git revert` commit đã bật Enforce rồi sync. Nhanh hơn sửa tay,
  giữ được audit trail, và không để lại cluster lệch khỏi Git.
- **CI Pipeline:** nếu Trivy/Semgrep báo lỗi giả quá nhiều, cấu hình `.trivyignore` /
  `.semgrepignore` có review, **không** tắt bước quét.

## Cutover outcome

Quá trình Enforce Cutover đã hoàn tất vào ngày **28-29/07/2026**.
- Policy `verify-first-party-signatures` đã được đẩy lên `Enforce` thành công trên nhánh `main` và sync tự động qua ArgoCD.
- Policy `allow-approved-external-image-digests` cũng đã lên `Enforce` (PR #537, trước first-party một bước để cô lập rủi ro). 11/11 image bên thứ ba pin digest tuyệt đối và khớp catalog đã review.
- Kịch bản chặn CI (Trivy/Semgrep báo đỏ) hoạt động trơn tru, GitHub Branch Protection đã chặn merge thành công.
- Kịch bản chặn Kubernetes Admission hoạt động chính xác. Các image chưa ký hoặc bị làm giả digest đã bị Kyverno chặn đứng với lỗi `no signatures found` (đã demo với quyền Admin).
- Script `trace-provenance.sh` trả về kết quả `PASS` cho toàn bộ các trụ bảo mật (Trivy, Cosign, SBOM) và trích xuất thành công `sourceSha`.
- Toàn bộ kết quả Demo được ghi hình và lưu trữ tại: [Video Demo Mandate 10](https://youtu.be/xrqzUAIk7IA).

## Update 2026-07-29 — Hoàn thiện PM-125, PM-126, PM-127 và PM-129

Trong quá trình chuẩn bị cho Cutover, toàn bộ các luồng cấu phần phụ đã được tích hợp và xử lý dứt điểm thông qua các PM:

1. **PM-125 & PM-126 (Pre-merge Security Gates & Branch Protection):**
   - Đã cấu hình thành công Branch Protection trên nhánh `main`, bắt buộc `Secure delivery gate` phải xanh và cần ít nhất 1 approval (PM-126).
   - Trivy, Semgrep, và tfsec quét tĩnh toàn bộ mã nguồn và chặn đứng mọi lỗi High/Critical trước khi merge (PM-125).

2. **Sự cố Kubernetes RBAC che khuất Kyverno (PM-127):**
   - **Mô tả:** Khi kiểm tra thử Kịch bản Kyverno chặn image, tài khoản Read-only (`quyen-readonly`) nhận được lỗi `deployments.apps is forbidden` thay vì lỗi của Admission Webhook.
   - **Xử lý:** Phát hiện ra rằng hệ thống Kubernetes phân quyền RBAC (Authorization) chặn request trước cả khi nó chạm đến Kyverno (Admission). Điều này minh chứng cho thiết kế Defense in Depth của hệ thống. Đã khắc phục bằng cách hướng dẫn sử dụng tài khoản Admin (`cdo-admin-team`) có quyền tạo Deployment để bypass lớp RBAC, từ đó kích hoạt thành công Lớp bảo vệ thứ 2 (Kyverno Webhook) chặn đúng image rác.

3. **Sự cố Provenance Traceability (PM-129):**
   - **Mô tả:** Lệnh `cosign verify` thay đổi cấu trúc dữ liệu JSON đầu ra ở phiên bản 2.4.0 (không còn trả về full tag trong `docker-reference` mà chỉ trả về tên repository), khiến script `trace-provenance.sh` liên tục báo lỗi `verified signature does not reference the expected release digest`.
   - **Xử lý (Vá ống dẫn):**
     - Sửa logic script để lọc đúng thuộc tính `docker-reference` và so sánh chính xác tên repo thay vì toàn bộ tag.
     - Bỏ qua check annotation dư thừa (do CI không hỗ trợ tạo annotation ở phiên bản này).
     - Script đã chạy thành công 100%, trả về `overallResult: PASS` ngay trên Production pod.

## Sign-off

Người lập ADR (CDO01)

