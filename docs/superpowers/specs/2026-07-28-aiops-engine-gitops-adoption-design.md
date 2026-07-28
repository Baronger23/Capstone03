# Đưa AIOps Engine (AIO02) vào GitOps — Thiết kế

## Trạng thái

- Thiết kế được duyệt trong hội thoại ngày 2026-07-28.
- **Phase 0 đã thực thi** (xoá ingress public) — có xác nhận trực tiếp của user trong
  hội thoại, xem mục "Phase 0" bên dưới.
- **Phase 1 đã thực thi xong ngày 2026-07-28** — adopt `aiops-engine` vào ArgoCD qua
  PR #519, merge lúc 09:40:30 UTC, commit `40078f0`. Không downtime — bằng chứng ở mục
  "Phase 1" bên dưới. PR #521 (gỡ label `managed-by` giả) là follow-up ngay sau.
- Phase 2–3 vẫn chỉ được duyệt ở mức thiết kế, **chưa cấp phép** mutation nào lên
  production ngoài những gì Phase 1 đã làm; mỗi phase đi qua PR riêng.

## Mục tiêu

Chuyển `aiops-engine` — workload của AIO02 đang chạy ngoài mọi hệ thống quản lý —
về dưới ArgoCD, đồng thời đóng các lỗ hổng bảo mật phát hiện trong quá trình khảo sát,
mà không làm gián đoạn khả năng phát hiện sự cố của engine.

Repo nguồn của AIO02: <https://github.com/DangThao195/AIO02_TF3_Phase3>

## Hiện trạng đã kiểm chứng (khảo sát 2026-07-28)

### Workload là "shadow" — không ai quản

`aiops-engine` chạy trong `techx-tf3` được 13 ngày, deploy bằng `kubectl apply` tay:

- `metadata.annotations."kubectl.kubernetes.io/last-applied-configuration"` có mặt;
- `deployment.kubernetes.io/revision: 68` — 68 lần apply tay;
- `argocd.argoproj.io/tracking-id` **rỗng** → không ArgoCD Application nào quản;
- label `app.kubernetes.io/managed-by: argocd` **có nhưng là giả**, dán tay, gây hiểu nhầm
  cho bất kỳ ai đọc cluster;
- 11 ReplicaSet tồn đọng — đây là `revisionHistoryLimit: 10` mặc định hoạt động đúng
  (10 cũ + 1 hiện tại), không phải lỗi; hạ xuống 3 là lựa chọn dọn dẹp.

**Repo AIO02 không phải nguồn sự thật, và lệch theo nhiều hướng:**

| Tài nguyên | Repo AIO02 | Live |
|---|---|---|
| Deployment image | `IF-v60` | `IF-v63` |
| CronJob image | `IF-v27` | **`IF-v25`** (lệch 38 bản so với engine) |
| RoleBinding subject | ServiceAccount `default` | ServiceAccount `aiops-engine` |
| Role rules | có `pods/exec: create`, `pods: delete` | **không có**; xem bên dưới |

Vì vậy nguồn để commit vào GitOps **bắt buộc là live state**, không phải file trong repo
AIO02 — bản repo còn bind quyền vào SA `default` (sẽ cấp quyền cho mọi workload không
chỉ định ServiceAccount).

Tài nguyên đang sống: `deployment/aiops-engine`, `service/aiops-engine`,
`cronjob/aiops-anomaly-training`, `serviceaccount/aiops-engine`,
`role/aiops-engine-role` + rolebinding, `secret/aiops-engine-secrets`,
`priorityclass/low-priority`. Tất cả đều ngoài GitOps.

### Lỗ hổng 1 — API điều khiển remediation mở ra Internet, không xác thực (đã đóng, Phase 0)

`ingress/aiops-engine-ingress` dùng `alb.ingress.kubernetes.io/scheme: internet-facing`
với `path: /remediation, pathType: Prefix`. Xác minh từ ngoài Internet trước khi xoá:

```
GET http://k8s-techxtf3-aiopseng-ac927793fa-767978147.ap-southeast-1.elb.amazonaws.com/remediation/mode
→ 200 {"status":"success","mode":"SLACK_HUMAN_APPROVAL","AUTO_REMEDIATION_LIVE_TEST":"False"}
```

`grep -rniE 'signing_secret|x-slack-signature|hmac|verify_slack' --include='*.py'` trên
toàn bộ `AIOps/aiops-engine/` cho **0 kết quả** — không có xác thực chữ ký Slack, không có
API key, không có `Depends` nào. Prefix `/remediation` phủ các endpoint mutating:

| Endpoint | Tác động nếu bị gọi từ ngoài |
|---|---|
| `POST /remediation/interactive` | duyệt hành động remediation bất kỳ (nhận JSON trần `{"action":"approve","incident_id":"..."}`) |
| `POST /remediation/approve` | như trên |
| `POST /remediation/mode` | đổi chế độ, kể cả sang tự động |
| `POST /remediation/stop` | kích hoạt emergency stop → vô hiệu hoá lưới an toàn AIOps |
| `POST /remediation/resume` | huỷ emergency stop |

Vi phạm trực tiếp Mandate #1 (least exposure) mà CDO01 đã báo PASS.

### Lỗ hổng 2 — pod mang credential admin toàn account

Deployment inject `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` từ
`secret/aiops-engine-secrets`. Truy vết access key đó:

```
IAM user aio2-admin-team → group AIO2-Admin → AdministratorAccess + AWSBillingReadOnlyAccess
```

ServiceAccount `aiops-engine` có annotation
`eks.amazonaws.com/role-arn: arn:aws:iam::197826770971:role/tf3-aiops-engine-irsa-role`
(thêm 2026-07-27), nhưng `aws iam get-role` trả `NoSuchEntity` — **role không tồn tại**.
Kể cả nếu có, env var `AWS_ACCESS_KEY_ID` vẫn đè lên IRSA trong chuỗi credential provider
của SDK. Engine hiện sống hoàn toàn nhờ key admin dài hạn.

Kết hợp lỗ hổng 1 + 2: một pod mang credential admin toàn account, đứng sau ALB public
không auth. (RBAC Kubernetes của SA thì tương đối chặt — xem Phase 3 — nên đường leo
thang chính là credential AWS trong env, không phải quyền trong cluster.)

### Lỗ hổng 3 — không có NetworkPolicy

`kubectl get netpol -n techx-tf3 | grep -c aiops` → `0`. Khớp với phần còn treo của
Mandate #17 đã ghi nhận trước đó.

### Vấn đề vận hành

- **ECR lifecycle không khớp tag.** Repo `tf-2-ai-engine` có rule "giữ 10 image tagged" với
  `tagPrefixList: ["v"]`, nhưng tag thật là `IF-v58`, `IF-v63`… bắt đầu bằng `IF`.
  Rule không bao giờ khớp → image ~200MB/bản tích luỹ vô hạn.
- **Ngoài supply-chain gate.** Repo `tf-2-ai-engine` tách khỏi `techx-corp`, không đi qua
  Trivy release gate / Cosign signing của PM-101. Không digest-pinned (PM-95).
  (Điểm tích cực: repo đã là `IMMUTABLE` + `scanOnPush: true`, nên tag không bị ghi đè.)
- **`imagePullPolicy: Always`** với tag immutable — kéo ảnh thừa mỗi lần khởi động pod.

### Ngoài phạm vi: chaos-engine

`AIOps/chaos-engine/` chỉ có `Dockerfile` + source Python + tài liệu, **không có manifest
Kubernetes nào**, và không có image tương ứng trong ECR (account chỉ có 3 repo:
`techx-corp`, `shopping-copilot`, `tf-2-ai-engine`). Đây là code phân tích chạy local,
không phải workload cluster → không có gì để GitOps quản lần này.

Chaos Mesh (công cụ OSS bơm lỗi) là thứ khác và đã nằm trong ArgoCD từ trước
(`gitops/apps/chaos-mesh-app.yaml`, auto-sync tắt có chủ đích).

Nếu sau này AIO02 xác nhận muốn deploy chaos-engine, làm spec riêng.

## Phạm vi

### Trong phạm vi

- đóng đường truy cập public không xác thực vào API remediation (Phase 0);
- đưa toàn bộ tài nguyên `aiops-engine` về dưới một ArgoCD Application (Phase 1);
- dựng IRSA thật và loại bỏ static admin key khỏi pod (Phase 2);
- NetworkPolicy, thu hẹp RBAC, digest-pin, dọn dẹp vận hành, khôi phục luồng duyệt
  qua Slack theo đường an toàn (Phase 3).

### Ngoài phạm vi

- `AIOps/chaos-engine/` (lý do ở trên);
- `AIE1/` (bản sao platform/chart — đã có trong repo này);
- `AIE2/shopping-copilot` (đã ở GitOps từ trước, `gitops/shopping-copilot/`);
- sửa code Python của engine (việc của AIO02 — chỗ nào cần, spec này chỉ nêu đề nghị);
- rà soát các shadow workload khác trong `techx-tf3` (ví dụ `cronjob/otel-logs-retention`)
  — đáng làm nhưng là việc riêng.

## Kiến trúc

### Ranh giới repo

Manifest đặt trong repo này (`Phase3-TF3-Infra-Sentinel`), **không** trỏ ArgoCD sang repo
AIO02. Lý do: repo AIO02 không có branch protection, gitleaks scan, hay review gate của
TF3; trỏ ArgoCD sang đó nghĩa là mọi push của họ vào thẳng production. Đặt ở đây thì
AIO02 sửa manifest qua PR, CDO01 giữ được quyền kiểm soát security/netpol.

Đây cũng đúng tiền lệ đã có với `shopping-copilot` (cũng là workload của AIO02):
manifest trần trong `gitops/shopping-copilot/`, Application riêng trong `gitops/apps/`.

### Vì sao manifest trần chứ không qua Helm chart

`aiops-engine` là image độc lập, không phải component của chart `techx-corp`. Đưa vào chart
sẽ phải mở rộng `values.schema.json` (`additionalProperties: false`) — rủi ro
`ComparisonError` làm chết cả pipeline, đã từng xảy ra với field `digest`. Manifest trần
giữ blast radius trong đúng một Application.

### Bố cục file

```
gitops/aiops-engine/
  deployment.yaml
  service.yaml
  serviceaccount.yaml
  rbac.yaml
  cronjob.yaml
  priorityclass.yaml
  networkpolicy.yaml        # thêm ở Phase 3
gitops/apps/aiops-engine-app.yaml
gitops/secrets/aiops-engine-secrets.yaml   # ExternalSecret, thêm ở Phase 2
```

`gitops/apps/aiops-engine-app.yaml` được app-of-apps `techx-corp-bootstrap` nhặt tự động
(nó watch `gitops/apps`), `path: gitops/aiops-engine`, `targetRevision: main`,
`namespace: techx-tf3`, `automated: {prune: true, selfHeal: true}` — giống
`shopping-copilot-app.yaml`.

## Các phase

### Phase 0 — Đóng đường public (ĐÃ THỰC THI 2026-07-28)

Ingress không do ArgoCD quản (không có tracking-id) nên xoá tay là sạch, không controller
nào sync lại.

Đã làm:

1. backup `kubectl get ingress aiops-engine-ingress -n techx-tf3 -o yaml` (37 dòng);
2. `kubectl delete ingress aiops-engine-ingress -n techx-tf3`.

Kết quả xác minh:

- `kubectl get ingress -n techx-tf3` chỉ còn `frontend-proxy-internal` (đúng thiết kế);
- `pod/aiops-engine-7cb74684f8-svqjf` vẫn `1/1 Running`, 0 restart;
- `curl` tới ALB cũ → `HTTP 000`, không kết nối được.

**Hệ quả phải thông báo cho AIO02:** nút Approve/Reject/Emergency-Stop trên Slack ngừng
hoạt động, vì Slack POST vào chính `/remediation/interactive` qua ALB này. Engine vẫn
thu thập telemetry, vẫn phát hiện bất thường, vẫn bắn cảnh báo Slack — chỉ là không
remediate được cho tới khi Phase 3 dựng lại đường an toàn. Đây là hướng fail-safe: thà
không tự sửa còn hơn để người lạ trên Internet bấm nút.

Phụ: bớt một ALB (~$16/tháng).

Việc còn lại của Phase 0: đưa backup manifest vào `docs/evidence/` và viết note gửi AIO02.

### Phase 1 — Adopt vào ArgoCD, không downtime

Nguyên tắc: **commit đầu tiên phải khớp live state**, không sửa gì. ArgoCD tạo Application
→ `Synced` ngay → không recreate pod. Mọi thay đổi thực chất để dành các PR sau.

Cách làm:

1. export live state từng tài nguyên, lọc field runtime (`status`, `metadata.uid`,
   `resourceVersion`, `creationTimestamp`, `generation`, `managedFields`,
   `last-applied-configuration`, `deployment.kubernetes.io/revision`, và các field
   `clusterIP`/`nodePort` do API server gán);
2. commit vào `gitops/aiops-engine/` + tạo `gitops/apps/aiops-engine-app.yaml`;
3. verify trước khi merge: `kubectl diff -k` hoặc `kubectl diff -f gitops/aiops-engine/`
   phải cho **rỗng**;
4. merge → ArgoCD sync → xác nhận `Synced/Healthy` và `deployment.kubernetes.io/revision`
   **không tăng** (bằng chứng pod không bị recreate);
5. PR nhỏ tiếp theo: gỡ label giả `app.kubernetes.io/managed-by: argocd` (giờ đã là thật
   qua tracking-id, label thủ công thành thừa và sai chuẩn).

Rủi ro cần canh: `prune: true` + `selfHeal: true` nghĩa là bất kỳ tài nguyên
`aiops-engine` nào tồn tại trong cluster mà không có trong git **sẽ bị xoá** ở lần sync
đầu. Vì vậy bước 1 phải liệt kê đủ, và bước 3 (`kubectl diff` rỗng) là cổng chặn bắt buộc.

**Kết quả thực thi (2026-07-28, PR #519, merge 09:40:30 UTC, commit `40078f0`).**

Bằng chứng zero-downtime, so trước/sau merge:

| Chỉ số | Trước merge | Sau merge |
|---|---|---|
| `deployment.kubernetes.io/revision` | 68 | 68 — không tăng |
| Pod | `aiops-engine-7cb74684f8-svqjf` | cùng tên pod — không bị recreate |
| RESTARTS | 0 | 0 |
| READY | 1/1 | `true` |

`argocd.argoproj.io/tracking-id` có mặt trên cả 7/7 tài nguyên sau sync. Gọi thử engine
qua cổng nội bộ sau khi Application `Synced` vẫn trả
`{"status":"success","mode":"SLACK_HUMAN_APPROVAL",...}` — hành vi không đổi so với
trước khi adopt.

PR #521 (follow-up ngay sau) gỡ label giả `app.kubernetes.io/managed-by: argocd` — nhãn
này giờ đã đúng thật qua tracking-id nên không cần dán tay nữa.

**Phát hiện mới — lộ ra khi adopt: CronJob training đang hỏng.**

Sau sync, ArgoCD báo Application health = `Degraded`, dù `sync = Synced` và cả 7 tài
nguyên đều `Synced` riêng lẻ. Nguyên nhân: hai Job con của `cronjob/aiops-anomaly-training`
đang ở trạng thái `Failed`:

| Job | Chạy cách đây | Kết quả |
|---|---|---|
| `aiops-anomaly-training-29741460` | 7 ngày | `Failed` |
| `aiops-anomaly-training-29751540` | 38 giờ | `Failed` |

Lý do fail: `DeadlineExceeded` — job chạy đủ `activeDeadlineSeconds: 3600` (1 giờ) rồi
bị giết, không phải crash. Job thứ hai bắt đầu `2026-07-26T19:00:00Z`, fail lúc
`20:00:00Z` — khớp đúng 3600 giây. Pod đã bị dọn (không còn log) nên không biết job treo
ở bước nào.

Nghi ngờ, chưa xác nhận: image CronJob là `IF-v25` trong khi engine chạy `IF-v63` — có
thể incompatibility ở `train_anomaly_model_eks.py`; hoặc credential S3 retry vô hạn
(cùng gốc với lỗ hổng 2 — static admin key, xem phần "Lỗ hổng 2" ở trên). Hệ quả: model
anomaly detection hiện tại có thể đã cũ ít nhất 2 tuần.

**Quyết định: cố ý KHÔNG xoá hai Job `Failed` này**, dù xoá đi là Application xanh
(`Healthy`) ngay lập tức. Hai Job đó là bằng chứng của một pipeline đang hỏng — xoá bằng
chứng trước khi điều tra là đi sai hướng. Đây là việc của AIO02, đã đưa vào "Việc cần
AIO02 xác nhận" bên dưới.

### Cảnh báo vận hành cho Phase 2/3 — `kubectl diff` không còn là cổng kiểm chứng sạch

Từ khi ArgoCD adopt xong (sau Phase 1), `kubectl diff -f gitops/aiops-engine/` **luôn**
hiện nhiễu cố định trên **mọi** tài nguyên trong thư mục, kể cả file không hề đụng tới:
annotation `argocd.argoproj.io/tracking-id` bị hiện như đang "bị xoá", và `generation`
tăng. Lý do: `kubectl diff` chạy dry-run apply phía client, không biết tới cơ chế
annotation-tracking của ArgoCD — nó coi field ArgoCD tự thêm là field lạ cần gỡ đi.

Đã kiểm chứng độc lập: dựng git worktree tạm ở commit trước khi có thay đổi thật, chạy
lại `kubectl diff` ở đó — nhiễu y hệt, tức là đã có sẵn ở baseline, không phải do PR đang
xét gây ra.

**Hệ quả:** tiêu chí "`kubectl diff` rỗng = an toàn" (dùng làm cổng chặn bắt buộc ở
Phase 1, bước 3) **không còn dùng được từ Phase 2 trở đi**. Thay bằng "diff có chọn
lọc": chấp nhận đúng pattern nhiễu đã biết (tracking-id + generation) cộng đúng những
dòng PR chủ đích đổi; bất kỳ dòng lạ nào khác ngoài hai nhóm đó là cảnh báo thật, phải
dừng lại kiểm tra trước khi merge.

### Phase 2 — IRSA thật, giết static admin key

Terraform trong `infra/live/production/`:

1. IAM role `tf3-aiops-engine-irsa`, trust policy OIDC của cluster, `sub` giới hạn đúng
   `system:serviceaccount:techx-tf3:aiops-engine`;
2. policy tối thiểu:
   - `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` trên
     `arn:aws:s3:::tf3-aiops-models-197826770971` và `/*`;
   - `bedrock:InvokeModel` trên `amazon.nova-lite-v1:0` và `amazon.nova-micro-v1:0`
     tại `us-east-1` (engine tự route Bedrock sang us-east-1 khi chạy ở ap-southeast-1);
   - `bedrock:Retrieve` / `bedrock:RetrieveAndGenerate` trên knowledge base `GH3FUCYVOJ`;
3. Secrets Manager secret `techx-tf3/aiops-slack-webhook` + cấp quyền đọc cho IRSA role
   của External Secrets Operator.

Sau khi `terraform apply tfplan`:

4. thêm `gitops/secrets/aiops-engine-secrets.yaml` — ExternalSecret dùng ClusterSecretStore
   `aws-secrets-manager` đã có, render secret chỉ chứa `slack-webhook-url`;
5. PR gỡ `AWS_ACCESS_KEY_ID` và `AWS_SECRET_ACCESS_KEY` khỏi **cả** Deployment và CronJob
   (chừng nào chưa gỡ thì IRSA có cũng vô nghĩa vì env var đè lên);
6. verify: pod restart, `/readyz` xanh, log không có `NoCredentialProviders`; gọi thử một
   luồng RCA để chứng minh Bedrock hoạt động; chạy tay một lần
   `aiops-anomaly-training` job để chứng minh S3 ghi được;
7. **phối hợp AIO02 vô hiệu hoá access key `AKIA…` của `aio2-admin-team`** — đây mới là
   bước đóng thật sự lỗ hổng 2. Trước đó phải xác nhận key này không được dùng ở chỗ khác
   (CI của AIO02, máy cá nhân…).

Thứ tự bắt buộc: dựng IRSA → verify engine chạy bằng IRSA → mới vô hiệu key. Đảo thứ tự
là engine chết.

### Phase 3 — Siết phần còn lại

**NetworkPolicy** (`gitops/aiops-engine/networkpolicy.yaml`). Egress cần:

| Đích | Cổng | Ghi chú |
|---|---|---|
| `prometheus` | 9090 | podSelector trong ns |
| `jaeger` | 16686 | podSelector trong ns |
| `opensearch` | 9200 | podSelector trong ns |
| CoreDNS | 53 UDP/TCP | **phải có `ipBlock 172.20.0.10/32`** |
| kube-apiserver | 443 | ipBlock endpoint EKS |
| AWS API (Bedrock/S3/Slack) | 443 | qua NAT |

Bài học đã trả giá 3 lần ở Mandate #17: trên VPC CNI, egress rule bằng `podSelector` tới
ClusterIP không hoạt động — mọi rule cần `ipBlock` ClusterIP `/32`. Xem postmortem 0012:
batch NetworkPolicy dùng podSelector thay ipBlock đã gây outage 30 phút ngày 20/07.

Ingress: chỉ cho `cloudflared` (sau khi Phase 3 dựng lại đường Slack), mặc định deny.

**RBAC.** Role live thực tế đã tương đối chặt:

```yaml
- apiGroups: ["apps"]
  resources: ["deployments", "deployments/scale"]
  verbs: ["get","list","watch","update","patch"]
- apiGroups: ["argoproj.io"]
  resources: ["rollouts", "rollouts/scale"]
  verbs: ["get","list","watch","update","patch"]
- apiGroups: [""]
  resources: ["pods","services","namespaces"]
  verbs: ["get","list","watch"]
```

Không có `pods/exec`, không có `pods: delete` — quyền ghi chỉ giới hạn ở scale/patch
deployment và Argo Rollout (bao gồm `checkout-rollout`). Đây là mức hợp lý cho một
remediation engine, **không cần siết thêm ở Phase 3**.

Việc thực sự cần làm: đảm bảo bản commit vào GitOps là **live state**, vì file
`AIOps/aiops-engine/k8s/rbac.yaml` trong repo AIO02 vừa rộng hơn (có `pods/exec: create`,
`pods: delete`) vừa bind sai vào ServiceAccount `default`. Nếu ai đó `kubectl apply` file
repo đè lên, RBAC sẽ nới rộng ngược. Sau khi vào GitOps, `selfHeal` sẽ tự revert — đó
chính là giá trị của việc adopt.

Đề nghị AIO02 xoá hoặc cập nhật `k8s/rbac.yaml` trong repo của họ để khỏi có hai nguồn
mâu thuẫn.

**Image và dọn dẹp.**

- digest-pin: `197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/tf-2-ai-engine@sha256:eea1d559d4314d6a840a7de2dd8b0ebb673348bf4732917023cf20f426cab66c`
  (chính là `IF-v63` đang chạy);
- đồng bộ image của CronJob với Deployment — live đang lệch `IF-v25` (cronjob) vs `IF-v63`
  (engine); cần AIO02 xác nhận `train_anomaly_model_eks.py` ở `IF-v63` còn tương thích;
- `imagePullPolicy: Always` → `IfNotPresent` (tag immutable + digest-pin thì Always là thừa);
- `revisionHistoryLimit: 3` trên Deployment (mặc định 10 → giữ 11 ReplicaSet; hạ xuống
  cho gọn, không phải sửa lỗi);
- sửa ECR lifecycle policy của `tf-2-ai-engine`: `tagPrefixList: ["v"]` → `["IF-v"]`.

**Khôi phục luồng duyệt Slack.** Thay ALB public bằng `cloudflared` đã chạy sẵn trong
cluster ($0, không thêm ALB): thêm public hostname riêng cho `/remediation/interactive`,
Cloudflare WAF giới hạn dải IP egress của Slack, bypass Access cho đúng path đó (Slack
không gửi được header service token nên không qua Access bình thường được).

Song song, đề nghị AIO02 thêm kiểm tra `X-Slack-Signature` (HMAC với `SLACK_SIGNING_SECRET`)
ở tầng app — đây mới là lớp phòng thủ đúng; WAF theo IP chỉ là bù đắp tạm.

## Tiêu chí thành công

| # | Tiêu chí | Cách verify |
|---|---|---|
| 1 | Không còn đường public tới API remediation | `curl` ALB cũ → không kết nối; `kubectl get ingress -n techx-tf3` không có aiops |
| 2 | `aiops-engine` do ArgoCD quản | Application `Synced/Healthy`; `argocd.argoproj.io/tracking-id` có mặt trên cả 7 tài nguyên |
| 3 | Adopt không gây downtime | `deployment.kubernetes.io/revision` không tăng sau sync đầu; pod `RESTARTS` không đổi |
| 4 | Pod không còn static AWS key | `kubectl get deploy aiops-engine -o yaml \| grep -c AWS_ACCESS_KEY_ID` → 0 |
| 5 | Engine vẫn gọi được Bedrock + S3 bằng IRSA | một luồng RCA chạy thành công; một lần chạy tay training job ghi được model lên S3 |
| 6 | Key admin của `aio2-admin-team` đã vô hiệu | `aws iam list-access-keys --user-name aio2-admin-team` → `Status: Inactive` hoặc key đã xoá |
| 7 | NetworkPolicy áp dụng, engine vẫn hoạt động | netpol tồn tại; `/readyz` xanh; engine vẫn query được Prometheus/Jaeger/OpenSearch |
| 8 | Image digest-pinned | manifest dùng `@sha256:`; ArgoCD `Synced` |
| 9 | Luồng duyệt Slack hoạt động lại | bấm Approve trên Slack → engine ghi audit log tương ứng |

## Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| ArgoCD prune xoá nhầm tài nguyên chưa kịp commit ở sync đầu | Cao | `kubectl diff` phải rỗng trước khi merge; liệt kê đủ 7 loại tài nguyên |
| Gỡ static key trước khi IRSA hoạt động → engine chết | Cao | Thứ tự bắt buộc: dựng IRSA → verify → mới gỡ key → mới vô hiệu key |
| Key `aio2-admin-team` còn dùng ở chỗ khác (CI, máy cá nhân) | Trung bình | Hỏi AIO02 trước; đặt `Inactive` (đảo được) chứ không xoá ngay |
| NetworkPolicy chặn nhầm → engine mất telemetry | Trung bình | Luôn kèm `ipBlock` ClusterIP `/32` cho DNS; áp từng rule, verify từng bước (bài học postmortem 0012) |
| AIO02 tiếp tục `kubectl apply` tay lên workload đã GitOps | Trung bình | `selfHeal: true` sẽ revert; thông báo rõ cho AIO02 rằng đường sửa giờ là PR |
| Mất luồng duyệt Slack trong lúc chờ Phase 3 | Thấp | Chấp nhận có chủ đích — fail-safe; AIO02 vẫn nhận được cảnh báo |

## Việc cần AIO02 xác nhận

1. Access key `AKIA…` của `aio2-admin-team` có đang dùng ở đâu khác không?
2. CronJob training đang chạy `IF-v25` trong khi engine ở `IF-v63` — nâng cronjob lên
   `IF-v63` có an toàn không, hay `train_anomaly_model_eks.py` đã đổi interface?
   Và `k8s/rbac.yaml` trong repo AIO02 (rộng hơn live, bind sai SA `default`) có nên xoá?
3. Hai Job `aiops-anomaly-training-29741460` (7 ngày trước) và `-29751540` (38 giờ
   trước) đều `Failed` do `DeadlineExceeded` (hết 3600s) — pipeline training treo ở
   bước nào? Model anomaly hiện tại đã cũ bao lâu, và có đang ảnh hưởng chất lượng
   phát hiện bất thường không?
4. `chaos-engine` có kế hoạch deploy lên cluster không?
5. Có đồng ý thêm xác thực chữ ký Slack ở tầng app không?

## Tham chiếu

- Repo nguồn AIO02: <https://github.com/DangThao195/AIO02_TF3_Phase3>
- Tiền lệ: `gitops/shopping-copilot/`, `gitops/apps/shopping-copilot-app.yaml`
- `docs/postmortem/0012-mandate5-networkpolicy-batch-outage.md` — bài học NetworkPolicy
  trên VPC CNI
- `docs/adr/0004-mandate-01-cdo01-envoy-least-exposure.md` — Mandate #1 least exposure
- `docs/adr/0008-pm-101-image-supply-chain-gate.md` — supply-chain gate
