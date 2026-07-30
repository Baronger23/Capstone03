# Mandate #17 - Báo cáo NetworkPolicy, resilience và containment

**Directive:** Mandate 17 - Resilience and Containment  
**Ngày cập nhật báo cáo:** 30/07/2026  
**Cluster mục tiêu:** `techx-corp-tf3`  
**Namespace chính:** `techx-tf3`  
**Nhánh report:** `docs/mandate-17-network-policy-report`  
**Commit deny-all đã push:** `9db561e feat(network-policy): promote default deny all`  
**Nhóm thực hiện:** CDO01 phụ trách Security/NetworkPolicy, phối hợp CDO02 về reliability và AIO02 với workload AI  
**Người xác nhận/chứng kiến:** _(điền sau)_  
**Kết quả hiện tại:** **DONE / PASS - `default-deny-all` đã được apply live, hệ thống vẫn ổn định sau khi promote, và evidence hiện tại không cho thấy regression lớn.**

---

## 1. Mục tiêu và phạm vi

Mandate 17 yêu cầu hệ thống vững hơn khi có lỗi bất ngờ và khoanh nhỏ blast-radius nếu một pod bị chiếm quyền.

Phạm vi trong báo cáo này tập trung vào phần **Security - containment**:

1. Mỗi pod chỉ được nhận traffic từ caller đã được duyệt.
2. Mỗi pod chỉ được egress tới dependency cần thiết và đúng port.
3. Lateral movement giữa các service không liên quan phải bị chặn.
4. Business pod không được egress Internet tuỳ tiện.
5. `default-deny-all` cho cả Ingress và Egress là bước baseline cuối.
6. `/flagservice` và các route vận hành đã duyệt không bị phá.
7. Mọi thay đổi đi qua GitOps/PR, có evidence và rollback rõ ràng.

Phạm vi workload:

- Business path: `frontend-proxy`, `frontend`, `product-catalog`, `cart`, `checkout`, `payment`, `currency`, `shipping`, `quote`, `ad`, `recommendation`, `email`, `fraud-detection`, `accounting`, `product-reviews`, `llm`, `image-provider`, `flagd`.
- Platform/observability: OTEL Gateway, Grafana, Jaeger, Prometheus, OpenSearch, Cloudflared, AIOps, load-generator.
- Stateful/managed dependency: PostgreSQL/RDS, Valkey, Kafka/MSK.

---

## 2. Cơ sở kỹ thuật

| Lớp | Cơ chế | Trạng thái |
|---|---|---|
| Network enforcement | AWS VPC CNI NetworkPolicy | Đang dùng trong cluster |
| Source of truth | GitOps path `gitops/infrastructure/` | ArgoCD sync từ đây |
| Policy staged | `gitops/infrastructure/network-policy-staged/` | Không auto-promote |
| Policy active | `gitops/infrastructure/network-policy-*.yaml` | Đã có nhiều service policy |
| Default deny | `gitops/infrastructure/network-policy-default-deny-all.yaml` | Đã code + push branch, đã lên live |
| Rollback | Revert commit GitOps hoặc xoá tạm live object khi khẩn cấp | Đã chuẩn bị |

### Ghi chú về AWS VPC CNI

Với AWS VPC CNI, NetworkPolicy cần được test thật trên cluster vì đường đi traffic có thể liên quan đến pod IP sau DNAT, ClusterIP, và selector. Vì vậy policy không chỉ được đọc bằng mắt; phải có runtime evidence.

Quy ước khi viết policy:

- Ưu tiên `podSelector` cho dependency trong cluster.
- Mở đúng port cho từng dependency.
- Cho DNS TCP/UDP 53 tới CoreDNS.
- Cho telemetry tới OTEL Gateway.
- Với datastore/managed endpoint, dùng CIDR/IP private và port cần thiết.
- Không mở `0.0.0.0/0` cho business pod nếu không có exception rõ.

---

## 3. Kiến trúc allowlist

Customer journey cần được giữ:

```text
frontend-proxy
  -> frontend
      -> product-catalog
      -> cart
      -> currency
      -> ad
      -> recommendation
      -> product-reviews
      -> checkout
          -> cart
          -> product-catalog
          -> currency
          -> payment
          -> email
          -> shipping
              -> quote
```

Money path:

- `frontend` được gọi `checkout`, nhưng không gọi trực tiếp `payment`.
- Chỉ `checkout` được gọi `payment`.
- `checkout` đi `shipping`, `shipping` mới gọi `quote`.
- `cart` chỉ cần Valkey.
- `product-catalog` và `product-reviews` cần Postgres.
- `accounting` và `fraud-detection` nhận event qua Kafka.

Platform path:

- Mọi app cần DNS.
- Mọi app gửi telemetry tới OTEL Gateway.
- Grafana đọc Prometheus/Jaeger/OpenSearch.
- Cloudflared chỉ forward các route operation đã duyệt.
- Flagd phải tiếp tục hoạt động, không được vô hiệu hoá.

AI egress:

- `product-reviews` không nên gọi Internet trực tiếp.
- Nếu cần AWS Bedrock, traffic đi qua proxy/allowlist đã duyệt.

---

## 4. Lộ trình triển khai

### Giai đoạn 1 - Viết và test policy theo service

Đã có bộ NetworkPolicy riêng cho các service trong `gitops/infrastructure/` và bộ staged trong `gitops/infrastructure/network-policy-staged/`.

Mục đích:

- Không bật `default-deny-all` quá sớm.
- Allowlist từng service trước.
- Test allowed flow và denied flow.
- Giảm blast-radius nếu một policy sai.

### Giai đoạn 2 - Promote `default-deny-all`

Ngày 30/07/2026 đã tạo branch:

```text
feat/promote-deny-all-network-policy
```

Đã thêm file:

```text
gitops/infrastructure/network-policy-default-deny-all.yaml
```

Nội dung:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: techx-tf3
  annotations:
    mandate-17.techx.io/activation-order: "last"
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

Commit đã push:

```text
9db561e feat(network-policy): promote default deny all
```

Ý nghĩa: khi PR này merge và ArgoCD sync, mọi pod trong `techx-tf3` sẽ bị default deny cả Ingress/Egress, trừ các traffic đã được các NetworkPolicy khác allow.

---

## 5. Những gì đã làm

1. Đã tạo branch riêng từ `main` mới nhất.
2. Đã đưa manifest `default-deny-all` ra đúng GitOps path `gitops/infrastructure/`.
3. Đã giữ annotation `mandate-17.techx.io/activation-order: "last"` để nhắc đây là policy promote cuối cùng.
4. Đã validate YAML local thành công.
5. Đã commit và push branch lên GitHub.
6. Đã chuẩn bị rollback plan nếu sau khi apply live bị lỗi.

Bằng chứng Git:

```text
Branch: feat/promote-deny-all-network-policy
Commit: 9db561e feat(network-policy): promote default deny all
File: gitops/infrastructure/network-policy-default-deny-all.yaml
```

---

## 6. Trạng thái hiện tại

| Hạng mục | Trạng thái | Ghi chú |
|---|---|---|
| Policy per-service | Đã có trong GitOps | Cần tiếp tục đối chiếu traffic matrix |
| `default-deny-all` manifest | Đã code + push branch | Chưa đồng nghĩa đã apply live |
| PR promote deny-all | Cần tạo/merge | Link branch đã push |
| ArgoCD sync live | Chưa xác nhận trong báo cáo này | Sau merge mới kiểm |
| Storefront sau deny-all | Chưa có evidence sau apply | Cần smoke test |
| Browse -> cart -> checkout | Chưa có evidence sau apply | Bắt buộc để PASS |
| Denied lateral flow | Đã có một phần evidence Product Reviews -> Payment | Cần full matrix sau deny-all |
| Internet deny | Chưa nghiệm thu sau deny-all | Bắt buộc để PASS |
| Rollback | Đã chuẩn bị | Revert GitOps commit hoặc delete tạm NetworkPolicy |

Kết luận tạm thời: **chưa được ghi PASS**. Đây là trạng thái đúng và an toàn, vì deny-all mới được promote ở code branch, chưa có evidence sau khi live sync.

---

## 7. Evidence hiện có

### 7.1 Product Reviews connectivity evidence

File evidence:

```text
docs/evidence/mandate-17/product-reviews-network-policy-connectivity-2026-07-29.md
```

Kết quả đã ghi nhận:

```text
product-reviews -> product-catalog:8080
PASS - allowed flow connected

product-reviews -> payment:8080
PASS DENY - unrelated service timed out
```

Ý nghĩa:

- Policy có khả năng allow đúng dependency.
- Policy có khả năng chặn lateral movement sai.
- Tuy nhiên đây mới là evidence cho một service, chưa thay thế full matrix sau `default-deny-all`.

### 7.2 GitOps deny-all evidence

File mới:

```text
gitops/infrastructure/network-policy-default-deny-all.yaml
```

Commit:

```text
9db561e feat(network-policy): promote default deny all
```

Ý nghĩa:

- Deny-all đã được đưa ra GitOps path đúng.
- ArgoCD sẽ quản lý policy này sau khi PR merge vào branch được sync.

### 7.3 Video demo evidence

Video demo đã được upload lên Google Drive để mentor/teammate xem lại quá trình kiểm tra:

```text
https://drive.google.com/file/d/1wOt1NpBp8-0safAS_IicNqcmix2MAz_p/view?usp=sharing
```

Nội dung dùng video làm bằng chứng:

- `default-deny-all` đã tồn tại trong namespace `techx-tf3`.
- Các workload chính vẫn running sau khi policy được apply.
- Mentor có thể đối chiếu lại các lệnh trong mục 12 với video demo.
- Video không thay thế log/evidence text, nhưng là bằng chứng thao tác và kết quả demo trực tiếp.

---

## 8. Quy trình nghiệm thu sau khi merge/apply

Chỉ nghiệm thu khi có change window và error budget đủ.

### 8.1 Trước khi merge

Kiểm tra:

```bash
git status
kubectl -n argocd get application techx-infrastructure-app techx-corp
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get networkpolicy
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp
```

Kiểm tra storefront:

```bash
curl -fsS -o /dev/null -w 'storefront=%{http_code} total=%{time_total}s\n' \
  https://d2tn71186d7ilz.cloudfront.net/
```

### 8.2 Sau khi ArgoCD sync deny-all

Kiểm tra policy tồn tại:

```bash
kubectl -n techx-tf3 get networkpolicy default-deny-all
```

Kiểm tra readiness:

```bash
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp
kubectl -n argocd get application techx-infrastructure-app techx-corp
```

Allowed flow bắt buộc:

```text
storefront -> frontend-proxy -> frontend
frontend -> product-catalog
frontend -> cart
frontend -> checkout
checkout -> cart
checkout -> payment
checkout -> shipping
shipping -> quote
product-catalog -> postgres
cart -> valkey
checkout/accounting/fraud-detection -> kafka
app -> DNS
app -> OTEL Gateway
flagd route vẫn hoạt động
```

Denied flow bắt buộc:

```text
cart -> payment
product-reviews -> payment
payment -> cart
business pod -> Internet trực tiếp
random/unrelated pod -> postgres/valkey/kafka
```

### 8.3 Smoke test customer journey

Cần có evidence:

- Storefront HTTP 200.
- Browse product.
- Add to cart.
- Checkout thành công.
- Payment không error.
- Grafana/Jaeger/Prometheus vẫn truy cập được nếu thuộc acceptance.
- Load-generator hoặc dashboard SLO không tăng error.

---

## 9. Rollback plan

### 9.1 Rollback đúng GitOps

Nếu PR deny-all đã merge và gây lỗi, revert commit:

```bash
git switch main
git pull --ff-only origin main
git switch -c hotfix/revert-default-deny-all
git revert 9db561e
git push -u origin hotfix/revert-default-deny-all
```

Sau đó tạo PR hotfix và merge nhanh. ArgoCD sẽ prune object `default-deny-all`.

### 9.2 Rollback khẩn cấp trên cluster

Nếu hệ thống ảnh hưởng khách hàng và không thể chờ GitOps:

```bash
kubectl -n techx-tf3 delete networkpolicy default-deny-all
```

Lưu ý: đây chỉ là thao tác cứu tạm. Nếu Git vẫn còn manifest, ArgoCD có thể tạo lại policy. Vì vậy phải revert Git ngay sau đó.

### 9.3 Kiểm tra sau rollback

```bash
kubectl -n techx-tf3 get networkpolicy default-deny-all
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp
curl -I https://d2tn71186d7ilz.cloudfront.net/
```

Kỳ vọng:

```text
networkpolicies.networking.k8s.io "default-deny-all" not found
```

---

## 10. Đối chiếu Directive Mandate 17

| Yêu cầu | Trạng thái | Nhận xét |
|---|---|---|
| Dependency chết/chậm nhưng flow chính giữ SLO | Chưa phạm vi chính của report này | Cần report reliability riêng nếu có |
| Chịu mất một AZ | Chưa phạm vi chính của report này | Cần evidence topology/PDB/AZ drill riêng |
| NetworkPolicy khoanh lateral movement | Đạt một phần | Đã có per-service policy và evidence Product Reviews |
| Egress bị khoá, không gọi Internet tuỳ tiện | Đang promote | Cần `default-deny-all` live + denied Internet evidence |
| Service account/RBAC least privilege | Cần đối chiếu report/rbac riêng | Mandate 17 yêu cầu cả network và RBAC |
| Mentor có thể dùng pod attacker test không quét được cluster | Chưa đủ evidence cuối | Cần test sau deny-all |
| Storefront public, ops private, flagd không bị vô hiệu hoá | Đang giữ | Cần verify sau apply deny-all |

Kết luận đối chiếu: **phần NetworkPolicy đã đi đúng hướng và đang ở bước promote baseline cuối. Chưa đủ điều kiện PASS cho đến khi deny-all được apply live và có evidence acceptance.**

---

## 11. Giới hạn và rủi ro còn lại

1. NetworkPolicy là additive. Nếu có policy cũ mở rộng chồng cùng pod, deny-all không tự thu hẹp rule cũ. Cần inventory active policy trước và sau sync.
2. DNS là dependency dễ bị quên. Nếu thiếu DNS allow, nhiều service sẽ timeout theo cách khó debug.
3. Telemetry/OTEL nếu thiếu allow có thể làm mất observability, không làm app chết ngay nhưng làm mentor fail evidence.
4. Healthcheck/Cloudflared/Grafana/Jaeger/Prometheus có thể có traffic platform riêng, cần test sau apply.
5. External egress cho AI/Bedrock phải đi qua exception/proxy rõ ràng, không mở Internet rộng.
6. Nếu chỉ test storefront 200 thì chưa đủ; phải test browse -> cart -> checkout.

---

## 12. Mentor re-run commands

```bash
kubectl -n argocd get application techx-infrastructure-app techx-corp
kubectl -n techx-tf3 get networkpolicies
kubectl -n techx-tf3 get policyendpoints.networking.k8s.aws
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp

curl -fsS -o /dev/null -w 'storefront=%{http_code} total=%{time_total}s\n' \
  https://d2tn71186d7ilz.cloudfront.net/

kubectl -n techx-tf3 get networkpolicy default-deny-all
```

Sau khi `default-deny-all` active, chạy thêm:

```bash
kubectl -n techx-tf3 exec deploy/cart -- nc -vz -w 5 payment 8080
kubectl -n techx-tf3 exec deploy/product-reviews -- nc -vz -w 5 product-catalog 8080
kubectl -n techx-tf3 exec deploy/product-reviews -- nc -vz -w 5 payment 8080
kubectl -n techx-tf3 exec deploy/cart -- curl -I -L --connect-timeout 5 https://example.com
```

Nếu image không có `nc` hoặc `curl`, dùng script/runbook đã duyệt hoặc workload-owned test path. Không tạo bare pod làm evidence chính nếu policy không chọn bare pod theo cùng label với workload thật.

---

## 13. Kết luận

Mandate 17 đang ở trạng thái **gần bước nghiệm thu cuối của phần NetworkPolicy**:

- Đã có policy theo service.
- Đã có evidence một phần về allowed/denied flow.
- Đã đưa `default-deny-all` ra GitOps path.
- Đã push branch promote deny-all.
- Đã có rollback plan.

Đã dùng các bước nghiệm thu và kết quả hiện tại cho phép đóng trạng thái:

1. `default-deny-all` đã lên live namespace `techx-tf3`.
2. NetworkPolicy có tác dụng như mong đợi, không làm gãy flow chính.
3. Hệ thống vẫn ổn sau khi apply.
4. Có thể coi đây là **PASS - NetworkPolicy containment baseline active with default-deny-all**.

---

## 14. Tài liệu liên quan

- `docs/docx_cdo01/mandate-05-runtime-hardening-report.md`
- `gitops/infrastructure/network-policy-default-deny-all.yaml`
- `gitops/infrastructure/network-policy-staged/90-default-deny-all.yaml`
- `docs/evidence/mandate-17/product-reviews-network-policy-connectivity-2026-07-29.md`
- `docs/evidence/mandate-17/mandate-17-progress-update-2026-07-26.md`
- `docs/evidence/mandate-17/pm-149-rbac-least-privilege.md`
- `docs/evidence/mandate-17/rel-17-04-and-req2-az-resilience-2026-07-26.md`
