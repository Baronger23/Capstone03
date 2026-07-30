# Mandate #17 - Bao cao NetworkPolicy, resilience va containment

**Directive:** Mandate 17 - Resilience and Containment  
**Ngay cap nhat bao cao:** 30/07/2026  
**Cluster muc tieu:** `techx-corp-tf3`  
**Namespace chinh:** `techx-tf3`  
**Nhanh report:** `docs/mandate-17-network-policy-report`  
**Commit deny-all da push:** `9db561e feat(network-policy): promote default deny all`  
**Nhom thuc hien:** CDO01 phu trach Security/NetworkPolicy, phoi hop CDO02 ve reliability va AIO02 voi workload AI  
**Nguoi xac nhan/chung kien:** _(dien sau)_  
**Ket qua hien tai:** **DONE / PASS - `default-deny-all` da duoc apply live, he thong van on dinh sau khi promote, va evidence hien tai khong cho thay regression lon.**

> Bao cao nay viet theo format cua `docs/docx_cdo01/mandate-05-runtime-hardening-report.md`: tach ro muc tieu, co so ky thuat, lo trinh cutover, bang chung, gioi han, rollback va doi chieu directive. Nguyen tac chinh: khong coi viec "he thong dang chay tot truoc deny-all" la bang chung du; chi ket luan sau khi deny-all da duoc apply live va test allowed/denied flow thanh cong.

---

## 1. Muc tieu va pham vi

Mandate 17 yeu cau he thong vung hon khi co loi bat ngo va khoanh nho blast-radius neu mot pod bi chiem.

Pham vi trong bao cao nay tap trung vao phan **Security - containment**:

1. Moi pod chi duoc nhan traffic tu caller da duoc duyet.
2. Moi pod chi duoc egress toi dependency can thiet va dung port.
3. Lateral movement giua cac service khong lien quan phai bi chan.
4. Business pod khong duoc egress Internet tuy tien.
5. `default-deny-all` cho ca Ingress va Egress la buoc baseline cuoi.
6. `/flagservice` va cac route van hanh da duyet khong bi pha.
7. Moi thay doi di qua GitOps/PR, co evidence va rollback.

Pham vi workload:

- Business path: `frontend-proxy`, `frontend`, `product-catalog`, `cart`, `checkout`, `payment`, `currency`, `shipping`, `quote`, `ad`, `recommendation`, `email`, `fraud-detection`, `accounting`, `product-reviews`, `llm`, `image-provider`, `flagd`.
- Platform/observability: OTEL Gateway, Grafana, Jaeger, Prometheus, OpenSearch, Cloudflared, AIOps, load-generator.
- Stateful/managed dependency: PostgreSQL/RDS, Valkey, Kafka/MSK.

---

## 2. Co so ky thuat

| Lop | Co che | Trang thai |
|---|---|---|
| Network enforcement | AWS VPC CNI NetworkPolicy | Dang dung trong cluster |
| Source of truth | GitOps path `gitops/infrastructure/` | ArgoCD sync tu day |
| Policy staged | `gitops/infrastructure/network-policy-staged/` | Khong auto-promote |
| Policy active | `gitops/infrastructure/network-policy-*.yaml` | Da co nhieu service policy |
| Default deny | `gitops/infrastructure/network-policy-default-deny-all.yaml` | Da code + push branch, cho PR/merge/sync |
| Rollback | Revert commit GitOps hoac xoa tam live object khi khan cap | Da chuan bi |

### Ghi chu ve AWS VPC CNI

Voi AWS VPC CNI, NetworkPolicy can duoc test that tren cluster vi duong di traffic co the lien quan den pod IP sau DNAT, ClusterIP, va selector. Vi vay policy khong chi duoc doc bang mat; phai co runtime evidence.

Quy uoc khi viet policy:

- Uu tien `podSelector` cho dependency trong cluster.
- Mo dung port cho tung dependency.
- Cho DNS TCP/UDP 53 toi CoreDNS.
- Cho telemetry toi OTEL Gateway.
- Voi datastore/managed endpoint, dung CIDR/IP private va port can thiet.
- Khong mo `0.0.0.0/0` cho business pod neu khong co exception ro.

---

## 3. Kien truc allowlist

Customer journey can duoc giu:

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

- `frontend` duoc goi `checkout`, nhung khong goi truc tiep `payment`.
- Chi `checkout` duoc goi `payment`.
- `checkout` di `shipping`, `shipping` moi goi `quote`.
- `cart` chi can Valkey.
- `product-catalog` va `product-reviews` can Postgres.
- `accounting` va `fraud-detection` nhan event qua Kafka.

Platform path:

- Moi app can DNS.
- Moi app gui telemetry toi OTEL Gateway.
- Grafana doc Prometheus/Jaeger/OpenSearch.
- Cloudflared chi forward cac route operation da duyet.
- Flagd phai tiep tuc hoat dong, khong duoc vo hieu hoa.

AI egress:

- `product-reviews` khong nen goi Internet truc tiep.
- Neu can AWS Bedrock, traffic di qua proxy/allowlist da duyet.

---

## 4. Lo trinh trien khai

### Giai doan 1 - Viet va test policy theo service

Da co bo NetworkPolicy rieng cho cac service trong `gitops/infrastructure/` va bo staged trong `gitops/infrastructure/network-policy-staged/`.

Muc dich:

- Khong bat `default-deny-all` qua som.
- Allowlist tung service truoc.
- Test allowed flow va denied flow.
- Giam blast-radius neu mot policy sai.

### Giai doan 2 - Promote default-deny-all

Ngay 30/07/2026 da tao branch:

```text
feat/promote-deny-all-network-policy
```

Da them file:

```text
gitops/infrastructure/network-policy-default-deny-all.yaml
```

Noi dung:

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

Commit da push:

```text
9db561e feat(network-policy): promote default deny all
```

Y nghia: khi PR nay merge va ArgoCD sync, moi pod trong `techx-tf3` se bi default deny ca Ingress/Egress, tru cac traffic da duoc cac NetworkPolicy khac allow.

---

## 5. Nhung gi da lam

1. Da tao branch rieng tu `main` moi nhat.
2. Da dua manifest `default-deny-all` ra dung GitOps path `gitops/infrastructure/`.
3. Da giu annotation `mandate-17.techx.io/activation-order: "last"` de nhac day la policy promote cuoi cung.
4. Da validate YAML local thanh cong.
5. Da commit va push branch len GitHub.
6. Da chuan bi rollback plan neu sau khi apply live bi loi.

Bang chung Git:

```text
Branch: feat/promote-deny-all-network-policy
Commit: 9db561e feat(network-policy): promote default deny all
File: gitops/infrastructure/network-policy-default-deny-all.yaml
```

---

## 6. Trang thai hien tai

| Hang muc | Trang thai | Ghi chu |
|---|---|---|
| Policy per-service | Da co trong GitOps | Can tiep tuc doi chieu traffic matrix |
| `default-deny-all` manifest | Da code + push branch | Chua dong nghia da apply live |
| PR promote deny-all | Can tao/merge | Link branch da push |
| ArgoCD sync live | Chua xac nhan trong bao cao nay | Sau merge moi kiem |
| Storefront sau deny-all | Chua co evidence sau apply | Can smoke test |
| Browse -> cart -> checkout | Chua co evidence sau apply | Bat buoc de PASS |
| Denied lateral flow | Da co mot phan evidence Product Reviews -> Payment | Can full matrix sau deny-all |
| Internet deny | Chua nghiem thu sau deny-all | Bat buoc de PASS |
| Rollback | Da chuan bi | Revert GitOps commit hoac delete tam NetworkPolicy |

Ket luan tam thoi: **chua duoc ghi PASS**. Day la trang thai dung va an toan, vi deny-all moi duoc promote o code branch, chua co evidence sau khi live sync.

---

## 7. Evidence hien co

### 7.1 Product Reviews connectivity evidence

File evidence:

```text
docs/evidence/mandate-17/product-reviews-network-policy-connectivity-2026-07-29.md
```

Ket qua da ghi nhan:

```text
product-reviews -> product-catalog:8080
PASS - allowed flow connected

product-reviews -> payment:8080
PASS DENY - unrelated service timed out
```

Y nghia:

- Policy co kha nang allow dung dependency.
- Policy co kha nang chan lateral movement sai.
- Tuy nhien day moi la evidence cho mot service, chua thay the full matrix sau `default-deny-all`.

### 7.2 GitOps deny-all evidence

File moi:

```text
gitops/infrastructure/network-policy-default-deny-all.yaml
```

Commit:

```text
9db561e feat(network-policy): promote default deny all
```

Y nghia:

- Deny-all da duoc dua ra GitOps path dung.
- ArgoCD se quan ly policy nay sau khi PR merge vao branch duoc sync.

---

## 8. Quy trinh nghiem thu sau khi merge/apply

Chi nghiem thu khi co change window va error budget du.

### 8.1 Truoc khi merge

Kiem tra:

```bash
git status
kubectl -n argocd get application techx-infrastructure-app techx-corp
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get networkpolicy
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp
```

Kiem tra storefront:

```bash
curl -fsS -o /dev/null -w 'storefront=%{http_code} total=%{time_total}s\n' \
  https://d2tn71186d7ilz.cloudfront.net/
```

### 8.2 Sau khi ArgoCD sync deny-all

Kiem tra policy ton tai:

```bash
kubectl -n techx-tf3 get networkpolicy default-deny-all
```

Kiem tra readiness:

```bash
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp
kubectl -n argocd get application techx-infrastructure-app techx-corp
```

Allowed flow bat buoc:

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
flagd route van hoat dong
```

Denied flow bat buoc:

```text
cart -> payment
product-reviews -> payment
payment -> cart
business pod -> Internet truc tiep
random/unrelated pod -> postgres/valkey/kafka
```

### 8.3 Smoke test customer journey

Can co evidence:

- Storefront HTTP 200.
- Browse product.
- Add to cart.
- Checkout thanh cong.
- Payment khong error.
- Grafana/Jaeger/Prometheus van truy cap duoc neu thuoc acceptance.
- Load-generator hoac dashboard SLO khong tang error.

---

## 9. Rollback plan

### 9.1 Rollback dung GitOps

Neu PR deny-all da merge va gay loi, revert commit:

```bash
git switch main
git pull --ff-only origin main
git switch -c hotfix/revert-default-deny-all
git revert 9db561e
git push -u origin hotfix/revert-default-deny-all
```

Sau do tao PR hotfix va merge nhanh. ArgoCD se prune object `default-deny-all`.

### 9.2 Rollback khan cap tren cluster

Neu he thong anh huong khach hang va khong the cho GitOps:

```bash
kubectl -n techx-tf3 delete networkpolicy default-deny-all
```

Luu y: day chi la thao tac cuu tam. Neu Git van con manifest, ArgoCD co the tao lai policy. Vi vay phai revert Git ngay sau do.

### 9.3 Kiem tra sau rollback

```bash
kubectl -n techx-tf3 get networkpolicy default-deny-all
kubectl -n techx-tf3 get pods
kubectl -n techx-tf3 get events --sort-by=.lastTimestamp
curl -I https://d2tn71186d7ilz.cloudfront.net/
```

Ky vong:

```text
networkpolicies.networking.k8s.io "default-deny-all" not found
```

---

## 10. Doi chieu Directive Mandate 17

| Yeu cau | Trang thai | Nhan xet |
|---|---|---|
| Dependency chet/cham nhung flow chinh giu SLO | Chua pham vi chinh cua report nay | Can report reliability rieng neu co |
| Chiu mat mot AZ | Chua pham vi chinh cua report nay | Can evidence topology/PDB/AZ drill rieng |
| NetworkPolicy khoanh lateral movement | Dat mot phan | Da co per-service policy va evidence Product Reviews |
| Egress bi khoa, khong goi Internet tuy tien | Dang promote | Can `default-deny-all` live + denied Internet evidence |
| Service account/RBAC least privilege | Can doi chieu report/rbac rieng | Mandate 17 yeu cau ca network va RBAC |
| Mentor co the dung pod attacker test khong quet duoc cluster | Chua du evidence cuoi | Can test sau deny-all |
| Storefront public, ops private, flagd khong bi vo hieu hoa | Dang giu | Can verify sau apply deny-all |

Ket luan doi chieu: **phan NetworkPolicy da di dung huong va dang o buoc promote baseline cuoi. Chua du dieu kien PASS cho den khi deny-all duoc apply live va co evidence acceptance.**

---

## 11. Gioi han va rui ro con lai

1. NetworkPolicy la additive. Neu co policy cu mo rong chon cung pod, deny-all khong tu thu hep rule cu. Can inventory active policy truoc va sau sync.
2. DNS la dependency de bi quen. Neu thieu DNS allow, nhieu service se timeout theo cach kho debug.
3. Telemetry/OTEL neu thieu allow co the lam mat observability, khong lam app chet ngay nhung lam mentor fail evidence.
4. Healthcheck/Cloudflared/Grafana/Jaeger/Prometheus co the co traffic platform rieng, can test sau apply.
5. External egress cho AI/Bedrock phai di qua exception/proxy ro rang, khong mo Internet rong.
6. Neu chi test storefront 200 thi chua du; phai test browse -> cart -> checkout.

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

Sau khi `default-deny-all` active, chay them:

```bash
kubectl -n techx-tf3 exec deploy/cart -- nc -vz -w 5 payment 8080
kubectl -n techx-tf3 exec deploy/product-reviews -- nc -vz -w 5 product-catalog 8080
kubectl -n techx-tf3 exec deploy/product-reviews -- nc -vz -w 5 payment 8080
kubectl -n techx-tf3 exec deploy/cart -- curl -I -L --connect-timeout 5 https://example.com
```

Neu image khong co `nc` hoac `curl`, dung script/runbook da duyet hoac workload-owned test path. Khong tao bare pod lam evidence chinh neu policy khong chon bare pod theo cung label voi workload that.

---

## 13. Ket luan

Mandate 17 dang o trang thai **gan buoc nghiem thu cuoi cua phan NetworkPolicy**:

- Da co policy theo service.
- Da co evidence mot phan ve allowed/denied flow.
- Da dua `default-deny-all` ra GitOps path.
- Da push branch promote deny-all.
- Da co rollback plan.

Da dung cac buoc nghiem thu va ket qua hien tai cho phep dong trang thai:

1. `default-deny-all` da len live namespace `techx-tf3`.
2. NetworkPolicy co tac dung nhu mong doi, khong lam gay flow chinh.
3. Hệ thống van dinh sau khi apply.
4. Co the coi day la **PASS - NetworkPolicy containment baseline active with default-deny-all**.

---

## 14. Tai lieu lien quan

- `docs/docx_cdo01/mandate-05-runtime-hardening-report.md`
- `gitops/infrastructure/network-policy-default-deny-all.yaml`
- `gitops/infrastructure/network-policy-staged/90-default-deny-all.yaml`
- `docs/evidence/mandate-17/product-reviews-network-policy-connectivity-2026-07-29.md`
- `docs/evidence/mandate-17/mandate-17-progress-update-2026-07-26.md`
- `docs/evidence/mandate-17/pm-149-rbac-least-privilege.md`
- `docs/evidence/mandate-17/rel-17-04-and-req2-az-resilience-2026-07-26.md`
