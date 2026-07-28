# AIOps Engine — Adopt vào ArgoCD (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đưa 7 tài nguyên `aiops-engine` đang chạy tay trong `techx-tf3` về dưới một ArgoCD Application, **không recreate pod, không thay đổi hành vi**.

**Architecture:** Manifest trần (không Helm) trong `gitops/aiops-engine/`, một Application trong `gitops/apps/aiops-engine-app.yaml` được app-of-apps `techx-corp-bootstrap` nhặt tự động. Theo đúng tiền lệ `shopping-copilot`. Nguyên tắc sống còn: **commit phải khớp live state byte-per-byte**, cổng chặn là `kubectl diff` cho output rỗng trước khi merge.

**Tech Stack:** Kubernetes 1.35 (EKS `techx-corp-tf3`), ArgoCD App-of-Apps, kubectl, git.

## Global Constraints

- Account production `197826770971`, region `ap-southeast-1`, cluster `techx-corp-tf3`, namespace `techx-tf3`.
- Máy này dùng AWS profile `default` (đã login đúng account) — **không** `export AWS_PROFILE=techx-new`, profile đó không tồn tại ở đây.
- kubectl đi qua SSM tunnel: chạy `scripts/kube-tunnel.sh` trước, tunnel tự đóng sau ~10–20 phút idle.
- **Không push thẳng `main`.** Branch từ `origin/main` sau `git fetch`, merge qua PR.
- **Không** commit secret giá trị thật vào file tracked.
- **Không** đụng `flagd` / `values-flagd-sync.yaml` / filter `envoy.filters.http.fault` — disqualify.
- Commit message **không** kèm `Co-Authored-By` hay chữ ký nền tảng (`.claude/rules/git.md`).
- Phase 1 **không sửa gì** về hành vi: không digest-pin, không đổi `imagePullPolicy`, không gỡ env AWS key, không thêm NetworkPolicy. Tất cả để Phase 2/3.
- Spec nguồn: `docs/superpowers/specs/2026-07-28-aiops-engine-gitops-adoption-design.md`.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `gitops/aiops-engine/deployment.yaml` | Deployment `aiops-engine` |
| `gitops/aiops-engine/service.yaml` | Service ClusterIP :80 → :8000 |
| `gitops/aiops-engine/serviceaccount.yaml` | SA + annotation IRSA (role chưa tồn tại — Phase 2 dựng) |
| `gitops/aiops-engine/rbac.yaml` | Role + RoleBinding (theo **live**, không theo repo AIO02) |
| `gitops/aiops-engine/cronjob.yaml` | CronJob `aiops-anomaly-training` |
| `gitops/aiops-engine/priorityclass.yaml` | PriorityClass `low-priority` (cluster-scoped) |
| `gitops/apps/aiops-engine-app.yaml` | ArgoCD Application |

Không tạo `networkpolicy.yaml` ở Phase 1 — thêm nó là thay đổi hành vi.

**Lưu ý về PriorityClass:** đây là tài nguyên **cluster-scoped**, không thuộc namespace `techx-tf3`. ArgoCD vẫn quản được (Application có `destination.namespace` chỉ là mặc định cho tài nguyên namespaced). Nó cũng có thể đang được workload khác dùng — task 5 kiểm tra điều này trước khi để `prune` chạm vào nó.

---

## Task 1: Tạo worktree và nhánh

**Files:** không có (thiết lập môi trường)

**Interfaces:**
- Produces: worktree sạch, nhánh `feature/aiops-engine-argocd-adoption` từ `origin/main`

- [ ] **Step 1: Mở tunnel EKS**

```bash
/home/tutruong/project/Phase3-TF3-Infra-Sentinel/scripts/kube-tunnel.sh
```

Expected: in ra danh sách link dashboard, không có dòng `❌ Failed`.

- [ ] **Step 2: Xác nhận kubectl thông và đang đúng cluster**

```bash
kubectl get deploy aiops-engine -n techx-tf3
```

Expected: `aiops-engine   1/1     1            1`

- [ ] **Step 3: Tạo worktree**

Dùng tool `EnterWorktree` (theo `.claude/rules/git.md` mục 3), branch name `feature/aiops-engine-argocd-adoption`, base `origin/main`.

Nếu không có tool đó:

```bash
cd /home/tutruong/project/Phase3-TF3-Infra-Sentinel
git fetch origin
git worktree add ../aiops-adoption -b feature/aiops-engine-argocd-adoption origin/main
cd ../aiops-adoption
```

- [ ] **Step 4: Xác nhận nhánh đúng gốc**

```bash
git rev-parse --abbrev-ref HEAD
git merge-base --is-ancestor origin/main HEAD && echo "OK: dựa trên origin/main"
```

Expected: `feature/aiops-engine-argocd-adoption` và `OK: dựa trên origin/main`

---

## Task 2: Export và làm sạch 7 manifest từ live state

**Files:**
- Create: `gitops/aiops-engine/deployment.yaml`
- Create: `gitops/aiops-engine/service.yaml`
- Create: `gitops/aiops-engine/serviceaccount.yaml`
- Create: `gitops/aiops-engine/rbac.yaml`
- Create: `gitops/aiops-engine/cronjob.yaml`
- Create: `gitops/aiops-engine/priorityclass.yaml`

**Interfaces:**
- Consumes: worktree từ Task 1
- Produces: 6 file YAML mà `kubectl diff` sẽ báo rỗng ở Task 3

**Vì sao phải lọc field:** API server tự gán `uid`, `resourceVersion`, `generation`, `creationTimestamp`, `managedFields`, `status`, và với Service là `clusterIP`/`ipFamilies`/`sessionAffinity`. Commit chúng vào git làm ArgoCD báo OutOfSync vĩnh viễn.

**Vì sao PHẢI giữ những field trông như rác:**

- `spec.template.metadata.annotations."kubectl.kubernetes.io/restartedAt"` — đây là dấu vết `kubectl rollout restart`. Nó nằm trong **pod template**, nên xoá nó đổi pod-template-hash → ReplicaSet mới → **pod restart**. Giữ nguyên.
- `spec.template.spec.serviceAccount: aiops-engine` (field deprecated, song song với `serviceAccountName`) — API server tự điền lại nếu bỏ. Giữ cho khỏi nhiễu diff.
- `app.kubernetes.io/managed-by: argocd` label giả — giữ ở Phase 1 để diff rỗng; gỡ ở Task 6 bằng một commit riêng.

- [ ] **Step 1: Tạo thư mục**

```bash
mkdir -p gitops/aiops-engine
```

- [ ] **Step 2: Viết `gitops/aiops-engine/deployment.yaml`**

```yaml
# Deployment aiops-engine (AIO02). Adopt vào ArgoCD 2026-07-28 — nội dung khớp
# nguyên trạng live state để sync đầu tiên không recreate pod.
#
# CHƯA sửa ở Phase 1, có chủ đích:
#   - AWS_ACCESS_KEY_ID/SECRET vẫn lấy từ secret (static key của aio2-admin-team).
#     Gỡ ở Phase 2 SAU khi IRSA role tf3-aiops-engine-irsa dựng xong trong Terraform.
#   - image dùng tag chứ chưa digest-pin; imagePullPolicy vẫn Always.
#   - annotation kubectl.kubernetes.io/restartedAt nằm trong pod template: xoá nó
#     sẽ đổi pod-template-hash và làm pod restart. Giữ nguyên.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aiops-engine
  namespace: techx-tf3
  labels:
    app: aiops-engine
    app.kubernetes.io/managed-by: argocd
    app.kubernetes.io/name: aiops-engine
spec:
  replicas: 1
  revisionHistoryLimit: 10
  progressDeadlineSeconds: 600
  selector:
    matchLabels:
      app: aiops-engine
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 25%
  template:
    metadata:
      annotations:
        kubectl.kubernetes.io/restartedAt: '2026-07-25T14:43:11+07:00'
      labels:
        app: aiops-engine
        app.kubernetes.io/name: aiops-engine
    spec:
      serviceAccount: aiops-engine
      serviceAccountName: aiops-engine
      dnsPolicy: ClusterFirst
      restartPolicy: Always
      schedulerName: default-scheduler
      terminationGracePeriodSeconds: 60
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: engine
        image: 197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/tf-2-ai-engine:IF-v63
        imagePullPolicy: Always
        ports:
        - name: http-metrics
          containerPort: 8000
          protocol: TCP
        env:
        - name: AIOPS_SIMULATION_MODE
          value: 'false'
        - name: PROMETHEUS_URL
          value: http://prometheus.techx-tf3.svc.cluster.local:9090
        - name: JAEGER_URL
          value: http://jaeger.techx-tf3.svc.cluster.local:16686/jaeger/ui
        - name: OPENSEARCH_URL
          value: http://opensearch.techx-tf3.svc.cluster.local:9200
        - name: SLACK_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: aiops-engine-secrets
              key: slack-webhook-url
              optional: true
        - name: AWS_ACCESS_KEY_ID
          valueFrom:
            secretKeyRef:
              name: aiops-engine-secrets
              key: aws-access-key-id
              optional: true
        - name: AWS_SECRET_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: aiops-engine-secrets
              key: aws-secret-access-key
              optional: true
        - name: AWS_DEFAULT_REGION
          value: ap-southeast-1
        - name: BEDROCK_AWS_REGION
          value: us-east-1
        - name: BEDROCK_MODEL_ID
          value: amazon.nova-lite-v1:0
        - name: BEDROCK_KB_ID
          value: GH3FUCYVOJ
        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        readinessProbe:
          httpGet:
            path: /readyz
            port: 8000
            scheme: HTTP
          initialDelaySeconds: 15
          periodSeconds: 10
          timeoutSeconds: 1
          successThreshold: 1
          failureThreshold: 3
        livenessProbe:
          httpGet:
            path: /readyz
            port: 8000
            scheme: HTTP
          initialDelaySeconds: 30
          periodSeconds: 30
          timeoutSeconds: 1
          successThreshold: 1
          failureThreshold: 3
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
        terminationMessagePath: /dev/termination-log
        terminationMessagePolicy: File
```

- [ ] **Step 3: Viết `gitops/aiops-engine/service.yaml`**

```yaml
# Service ClusterIP cho aiops-engine. clusterIP do API server gán nên không commit.
apiVersion: v1
kind: Service
metadata:
  name: aiops-engine
  namespace: techx-tf3
  labels:
    app.kubernetes.io/managed-by: argocd
    app.kubernetes.io/name: aiops-engine
spec:
  type: ClusterIP
  selector:
    app: aiops-engine
  ports:
  - name: http
    port: 80
    targetPort: 8000
    protocol: TCP
```

- [ ] **Step 4: Viết `gitops/aiops-engine/serviceaccount.yaml`**

```yaml
# ServiceAccount cho aiops-engine.
#
# CẢNH BÁO: annotation eks.amazonaws.com/role-arn dưới đây trỏ tới IAM role
# tf3-aiops-engine-irsa-role — role này KHÔNG TỒN TẠI (aws iam get-role trả
# NoSuchEntity, kiểm chứng 2026-07-28). Engine hiện chạy bằng static access key
# trong env, không phải IRSA. Giữ annotation nguyên trạng ở Phase 1 để diff rỗng;
# Phase 2 sẽ dựng role thật bằng Terraform rồi mới gỡ static key.
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aiops-engine
  namespace: techx-tf3
  labels:
    app.kubernetes.io/managed-by: argocd
    app.kubernetes.io/name: aiops-engine
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::197826770971:role/tf3-aiops-engine-irsa-role
```

- [ ] **Step 5: Viết `gitops/aiops-engine/rbac.yaml`**

```yaml
# Role + RoleBinding cho aiops-engine.
#
# QUAN TRỌNG: nội dung này lấy từ LIVE STATE, không phải từ file
# AIOps/aiops-engine/k8s/rbac.yaml trong repo AIO02. Bản repo đó rộng hơn
# (thêm pods/exec: create và pods: delete) và bind vào ServiceAccount "default"
# — nếu ai apply đè sẽ nới rộng quyền cho mọi workload không chỉ định SA.
# Sau khi vào GitOps, selfHeal sẽ tự revert những lần apply như vậy.
#
# Quyền ghi giới hạn ở scale/patch Deployment và Argo Rollout (gồm checkout-rollout);
# pods/services/namespaces chỉ đọc.
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: aiops-engine-role
  namespace: techx-tf3
  labels:
    app.kubernetes.io/managed-by: argocd
    app.kubernetes.io/name: aiops-engine
rules:
- apiGroups:
  - apps
  resources:
  - deployments
  - deployments/scale
  verbs:
  - get
  - list
  - watch
  - update
  - patch
- apiGroups:
  - argoproj.io
  resources:
  - rollouts
  - rollouts/scale
  verbs:
  - get
  - list
  - watch
  - update
  - patch
- apiGroups:
  - ''
  resources:
  - pods
  - services
  - namespaces
  verbs:
  - get
  - list
  - watch
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: aiops-engine-rolebinding
  namespace: techx-tf3
  labels:
    app.kubernetes.io/managed-by: argocd
    app.kubernetes.io/name: aiops-engine
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: aiops-engine-role
subjects:
- kind: ServiceAccount
  name: aiops-engine
  namespace: techx-tf3
```

- [ ] **Step 6: Viết `gitops/aiops-engine/cronjob.yaml`**

```yaml
# CronJob huấn luyện lại mô hình anomaly, 02:00 thứ Hai giờ VN (19:00 CN UTC).
#
# LƯU Ý DRIFT: image ở đây là IF-v25 trong khi engine chạy IF-v63 — lệch 38 bản.
# Giữ nguyên ở Phase 1 (nguyên tắc khớp live state). Nâng version là việc Phase 3,
# và phải hỏi AIO02 trước xem train_anomaly_model_eks.py ở IF-v63 còn tương thích.
#
# AWS_ACCESS_KEY_ID/SECRET cũng là static key — gỡ ở Phase 2 cùng lúc với Deployment.
apiVersion: batch/v1
kind: CronJob
metadata:
  name: aiops-anomaly-training
  namespace: techx-tf3
spec:
  schedule: 0 19 * * 0
  concurrencyPolicy: Forbid
  suspend: false
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      activeDeadlineSeconds: 3600
      template:
        spec:
          restartPolicy: OnFailure
          dnsPolicy: ClusterFirst
          schedulerName: default-scheduler
          priorityClassName: low-priority
          terminationGracePeriodSeconds: 30
          securityContext:
            runAsNonRoot: true
            runAsUser: 1000
            runAsGroup: 1000
            fsGroup: 1000
            seccompProfile:
              type: RuntimeDefault
          containers:
          - name: trainer
            image: 197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/tf-2-ai-engine:IF-v25
            imagePullPolicy: Always
            command:
            - python
            - train_anomaly_model_eks.py
            env:
            - name: PROMETHEUS_URL
              value: http://prometheus.techx-tf3.svc.cluster.local:9090
            - name: AIOPS_S3_BUCKET
              value: tf3-aiops-models-197826770971
            - name: AWS_REGION
              value: ap-southeast-1
            - name: AWS_ACCESS_KEY_ID
              valueFrom:
                secretKeyRef:
                  name: aiops-engine-secrets
                  key: aws-access-key-id
            - name: AWS_SECRET_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: aiops-engine-secrets
                  key: aws-secret-access-key
            resources:
              requests:
                cpu: 500m
                memory: 512Mi
              limits:
                cpu: '1'
                memory: 1Gi
            securityContext:
              allowPrivilegeEscalation: false
              runAsNonRoot: true
              runAsUser: 1000
              capabilities:
                drop:
                - ALL
            terminationMessagePath: /dev/termination-log
            terminationMessagePolicy: File
```

- [ ] **Step 7: Viết `gitops/aiops-engine/priorityclass.yaml`**

```yaml
# PriorityClass cho job huấn luyện — CLUSTER-SCOPED, không thuộc techx-tf3.
# Đảm bảo training job nhường tài nguyên cho pod production khi cụm chật.
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: low-priority
value: 1000
preemptionPolicy: PreemptLowerPriority
globalDefault: false
description: Low priority class for batch processing and training jobs.
```

- [ ] **Step 8: Commit**

```bash
git add gitops/aiops-engine/
git commit -m "feat(aiops): manifest aiops-engine từ live state, chưa gắn ArgoCD

Chụp nguyên trạng 6 tài nguyên đang chạy tay trong techx-tf3 (deployment,
service, serviceaccount, role+rolebinding, cronjob, priorityclass).

Nội dung lấy từ cluster chứ không từ repo AIO02 — repo đó lệch: RoleBinding
bind vào SA default, Role có thêm pods/exec và pods:delete, image cũ hơn.

Chưa có Application nên chưa ảnh hưởng gì tới cluster."
```

---

## Task 3: Cổng chặn — chứng minh manifest khớp live

**Files:** không tạo file; đây là task kiểm chứng

**Interfaces:**
- Consumes: 6 file từ Task 2
- Produces: bằng chứng `kubectl diff` rỗng — điều kiện bắt buộc để sang Task 4

**Vì sao đây là task riêng:** nếu diff không rỗng mà vẫn tạo Application với `prune: true` + `selfHeal: true`, ArgoCD sẽ ép cluster về bản trong git ngay lập tức — pod restart, hoặc tệ hơn là xoá tài nguyên không có trong git.

- [ ] **Step 1: Chạy diff**

```bash
kubectl diff -f gitops/aiops-engine/ ; echo "EXIT=$?"
```

Expected: `EXIT=0` và **không in ra dòng diff nào**.

`kubectl diff` trả exit code 1 khi có khác biệt, 0 khi giống. Nếu exit 1, đọc output và sửa file cho khớp live — **không** sửa cluster cho khớp file.

- [ ] **Step 2: Xử lý các khác biệt thường gặp**

Nếu diff báo khác ở những field sau thì đó là do API server tự điền, thêm chúng vào file cho khớp:

- Deployment/CronJob container thiếu `terminationMessagePath`, `terminationMessagePolicy`
- Pod spec thiếu `dnsPolicy`, `schedulerName`, `restartPolicy`, `terminationGracePeriodSeconds`
- CronJob thiếu `suspend: false`

Nếu diff báo khác ở `image`, `env`, `resources`, `rules` (RBAC) — **dừng lại**: nghĩa là có ai vừa apply tay lên cluster. Export lại live state và kiểm tra với AIO02 trước khi tiếp.

- [ ] **Step 3: Ghi lại bằng chứng**

```bash
mkdir -p docs/evidence/aiops-engine
kubectl diff -f gitops/aiops-engine/ > docs/evidence/aiops-engine/2026-07-28-kubectl-diff-before-adopt.txt 2>&1
echo "exit=$?" >> docs/evidence/aiops-engine/2026-07-28-kubectl-diff-before-adopt.txt
kubectl get deploy aiops-engine -n techx-tf3 \
  -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' \
  >> docs/evidence/aiops-engine/2026-07-28-kubectl-diff-before-adopt.txt
```

Ghi lại số revision hiện tại (đang là `68`) — Task 5 sẽ đối chiếu để chứng minh không recreate.

- [ ] **Step 4: Commit bằng chứng**

```bash
git add docs/evidence/aiops-engine/2026-07-28-kubectl-diff-before-adopt.txt
git commit -m "docs(aiops): bằng chứng kubectl diff rỗng trước khi adopt"
```

---

## Task 4: Tạo ArgoCD Application

**Files:**
- Create: `gitops/apps/aiops-engine-app.yaml`

**Interfaces:**
- Consumes: `gitops/aiops-engine/` từ Task 2, bằng chứng diff rỗng từ Task 3
- Produces: Application được `techx-corp-bootstrap` nhặt khi merge vào `main`

- [ ] **Step 1: Xác nhận app-of-apps đang watch `gitops/apps`**

```bash
kubectl get application techx-corp-bootstrap -n argocd \
  -o jsonpath='{.spec.source.path}{"\n"}{.spec.source.targetRevision}{"\n"}'
```

Expected: `gitops/apps` và `main`

- [ ] **Step 2: Viết `gitops/apps/aiops-engine-app.yaml`**

```yaml
# ArgoCD Application cho aiops-engine (workload AIOps của AIO02). App-of-apps
# techx-corp-bootstrap nhặt file này vì nó watch gitops/apps.
#
# Render manifest trần trong gitops/aiops-engine (không Helm): aiops-engine là image
# độc lập, không phải component của chart techx-corp, nên không đi qua
# values.schema.json (additionalProperties:false) — tránh rủi ro ComparisonError
# làm chết cả pipeline. Cùng lý do và cùng khuôn với shopping-copilot-app.yaml.
#
# Trước 2026-07-28 workload này chạy hoàn toàn ngoài GitOps: deploy bằng kubectl
# apply tay (revision 68), có dán label managed-by:argocd giả nhưng không
# Application nào quản. Manifest commit lần đầu khớp nguyên trạng live state nên
# sync đầu tiên không recreate pod.
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: aiops-engine
  namespace: argocd
spec:
  project: default
  source:
    repoURL: 'https://github.com/tuu-ngo/Phase3-TF3-Infra-Sentinel.git'
    targetRevision: main
    path: gitops/aiops-engine
  destination:
    server: 'https://kubernetes.default.svc'
    namespace: techx-tf3
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

- [ ] **Step 3: Xác nhận `repoURL` khớp với các Application khác**

```bash
grep -h 'repoURL' gitops/apps/shopping-copilot-app.yaml gitops/apps/aiops-engine-app.yaml
```

Expected: hai dòng giống hệt nhau. Sai repoURL là ArgoCD không tìm thấy path.

- [ ] **Step 4: Commit**

```bash
git add gitops/apps/aiops-engine-app.yaml
git commit -m "feat(aiops): ArgoCD Application cho aiops-engine

Đưa workload đang chạy ngoài GitOps (deploy tay, revision 68) về dưới
app-of-apps. Manifest khớp live state nên sync đầu không recreate pod."
```

- [ ] **Step 5: Mở PR**

```bash
git push -u origin feature/aiops-engine-argocd-adoption
gh pr create --base main \
  --title "feat(aiops): adopt aiops-engine vào ArgoCD (Phase 1)" \
  --body "$(cat <<'PRBODY'
## Bối cảnh

`aiops-engine` (workload AIOps của AIO02) chạy trong `techx-tf3` 13 ngày hoàn toàn
ngoài GitOps: deploy bằng `kubectl apply` tay, `deployment.kubernetes.io/revision: 68`,
có dán label `app.kubernetes.io/managed-by: argocd` **giả** nhưng không Application nào quản.

Thiết kế đầy đủ: `docs/superpowers/specs/2026-07-28-aiops-engine-gitops-adoption-design.md`

## PR này làm gì

Chụp nguyên trạng 6 tài nguyên từ **live state** vào `gitops/aiops-engine/` + tạo
ArgoCD Application. **Không thay đổi hành vi gì** — `kubectl diff -f gitops/aiops-engine/`
cho output rỗng (bằng chứng trong `docs/evidence/aiops-engine/`).

Nguồn là cluster chứ không phải repo AIO02, vì repo đó lệch nhiều hướng:
RoleBinding bind vào SA `default`, Role có thêm `pods/exec` + `pods: delete`, image cũ hơn.

## Chưa làm ở PR này (có chủ đích)

- static AWS key trong env vẫn còn — gỡ ở Phase 2, **sau khi** dựng IRSA role bằng Terraform
- chưa digest-pin, chưa NetworkPolicy, chưa đồng bộ image CronJob (`IF-v25` vs `IF-v63`)

## Kiểm tra sau khi merge

- [ ] Application `aiops-engine` Synced/Healthy
- [ ] `deployment.kubernetes.io/revision` vẫn là 68 (không recreate pod)
- [ ] pod `RESTARTS` không tăng
PRBODY
)"
```

---

## Task 5: Merge và xác minh sync không gây restart

**Files:** không có

**Interfaces:**
- Consumes: PR từ Task 4
- Produces: Application `Synced/Healthy`, bằng chứng zero-downtime

**Thời điểm:** làm trong giờ ít traffic.

**Cách lui đúng nếu sync sai: revert commit đã thêm `gitops/apps/aiops-engine-app.yaml`.**

`kubectl delete application aiops-engine -n argocd --cascade=orphan` **không hoạt động**
ở đây, dù nhìn giống thao tác lui an toàn chuẩn:

- Application mang `tracking-id: techx-corp-bootstrap:argoproj.io/Application:argocd/aiops-engine`.
  `techx-corp-bootstrap` chạy `prune+selfHeal` trên `gitops/apps` — hễ file
  `aiops-engine-app.yaml` còn trong git, Application bị xoá sẽ được **dựng lại trong
  ~3 phút**, quay lại đúng trạng thái trước khi "lui".
- `--cascade` của `kubectl delete` nói về ownerReference giữa các Kubernetes object, không
  phải cơ chế cascade-delete của ArgoCD (đó là field `resources-finalizer` trên chính
  Application). Cờ này không kiểm soát được ArgoCD sẽ prune hay giữ resource con.
- Application này **không có** finalizer `resources-finalizer.argocd.argoproj.io`, nên dù
  xoá kiểu gì (có hay không `--cascade=orphan`) resource con (Deployment, Service...)
  cũng tự động orphan — không phải rủi ro riêng của cờ `--cascade`, mà là mọi cách xoá
  Application này đều orphan.

Vì vậy lui đúng là **revert commit** đã thêm `gitops/apps/aiops-engine-app.yaml` (PR Task 4)
và merge lại vào `main`: `techx-corp-bootstrap` sẽ prune Application, workload
`aiops-engine` quay lại trạng thái "ngoài GitOps" như trước Phase 1 — không cần thao tác
`kubectl delete` tay nào, và không có Application nào bị dựng lại vì file gốc đã biến mất
khỏi git.

- [ ] **Step 1: Ghi lại trạng thái trước khi merge**

```bash
kubectl get deploy aiops-engine -n techx-tf3 \
  -o jsonpath='revision={.metadata.annotations.deployment\.kubernetes\.io/revision}{"\n"}'
kubectl get pod -n techx-tf3 -l app=aiops-engine \
  -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount,AGE:.metadata.creationTimestamp
```

Ghi lại 3 giá trị: revision, tên pod, restartCount.

- [ ] **Step 2: Kiểm tra PriorityClass có bị dùng chung không**

`low-priority` là cluster-scoped. Nếu workload ngoài `aiops-engine` cũng dùng nó, `prune` của Application này có thể xoá mất khi ai đó sửa file.

```bash
kubectl get pods -A -o json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print([ (p['metadata']['namespace'],p['metadata']['name']) for p in d['items'] if p['spec'].get('priorityClassName')=='low-priority' ])"
```

Expected: chỉ có pod của `aiops-anomaly-training` (hoặc danh sách rỗng nếu job không chạy). Nếu có workload khác dùng, ghi chú vào PR và cân nhắc tách PriorityClass sang `gitops/infrastructure/`.

- [ ] **Step 3: Merge PR**

Merge qua GitHub UI hoặc `gh pr merge --squash`. Branch protection trên `main` yêu cầu review + status check.

- [ ] **Step 4: Chờ ArgoCD sync và kiểm tra Application**

```bash
kubectl get application aiops-engine -n argocd \
  -o custom-columns=NAME:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status
```

Expected: `Synced   Healthy`. Nếu chưa thấy Application, đợi `techx-corp-bootstrap` sync trước (tối đa ~3 phút), hoặc bấm Refresh trên ArgoCD UI (`https://argocd.arthur-ngo.org`).

- [ ] **Step 5: CỔNG XÁC MINH — pod không bị recreate**

```bash
kubectl get deploy aiops-engine -n techx-tf3 \
  -o jsonpath='revision={.metadata.annotations.deployment\.kubernetes\.io/revision}{"\n"}'
kubectl get pod -n techx-tf3 -l app=aiops-engine \
  -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount,READY:.status.containerStatuses[0].ready
```

Expected: **revision y hệt Step 1** (68), **tên pod y hệt**, restartCount không tăng, `READY=true`.

Nếu revision tăng → pod đã bị recreate → manifest không khớp live. Không phải thảm hoạ (engine 1 replica, nó sẽ tự lên lại), nhưng phải tìm ra field nào lệch và ghi vào PR/postmortem note.

- [ ] **Step 6: Xác nhận tracking-id đã có trên cả 6 tài nguyên**

```bash
for r in deployment/aiops-engine service/aiops-engine serviceaccount/aiops-engine \
         role/aiops-engine-role rolebinding/aiops-engine-rolebinding \
         cronjob/aiops-anomaly-training; do
  printf '%-45s %s\n' "$r" \
    "$(kubectl get $r -n techx-tf3 -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/tracking-id}')"
done
printf '%-45s %s\n' priorityclass/low-priority \
  "$(kubectl get priorityclass low-priority -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/tracking-id}')"
```

Expected: cả 7 dòng đều có giá trị bắt đầu bằng `aiops-engine:` — không dòng nào rỗng.

- [ ] **Step 7: Xác nhận engine còn hoạt động thật**

```bash
kubectl exec -n techx-tf3 deploy/aiops-engine -- \
  python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/remediation/mode').read().decode())"
```

Expected: JSON có `"mode":"SLACK_HUMAN_APPROVAL"` — engine phản hồi bình thường qua cổng nội bộ (đường public đã đóng ở Phase 0).

---

## Task 6: Gỡ label `managed-by` giả

**Files:**
- Modify: `gitops/aiops-engine/deployment.yaml`, `service.yaml`, `serviceaccount.yaml`, `rbac.yaml`

**Interfaces:**
- Consumes: Application `Synced/Healthy` từ Task 5
- Produces: label thủ công biến mất, chỉ còn tracking-id thật của ArgoCD

**Vì sao tách khỏi Task 2:** label này nằm trên `metadata` của tài nguyên chứ **không** trong pod template, nên gỡ nó **không** làm pod restart. Nhưng phải làm sau khi ArgoCD đã quản thật — trước đó gỡ sẽ làm diff Task 3 không rỗng.

**Chỉ gỡ ở `metadata.labels` cấp tài nguyên.** Deployment còn có `app.kubernetes.io/name` trong `spec.template.metadata.labels` — **không đụng vào**, đó là pod template.

- [ ] **Step 1: Nhánh mới từ `origin/main`**

```bash
git fetch origin
git checkout -b chore/aiops-remove-fake-managed-by origin/main
```

- [ ] **Step 2: Gỡ label khỏi 4 file**

Xoá đúng một dòng `app.kubernetes.io/managed-by: argocd` trong `metadata.labels` của: Deployment, Service, ServiceAccount, Role, RoleBinding. Giữ nguyên `app.kubernetes.io/name`.

```bash
grep -rn 'managed-by: argocd' gitops/aiops-engine/
```

Expected sau khi sửa: không còn kết quả nào.

- [ ] **Step 3: Xác nhận pod template không bị đụng**

```bash
git diff -- gitops/aiops-engine/deployment.yaml
```

Kiểm tra bằng mắt: mọi dòng bị xoá phải nằm trong `metadata.labels` ở đầu file, **không** dòng nào nằm dưới `spec.template.metadata.labels`. Nếu lỡ xoá trong pod template → pod sẽ restart → hoàn tác.

- [ ] **Step 4: Diff so với cluster**

```bash
kubectl diff -f gitops/aiops-engine/
```

Expected: chỉ hiện các dòng `-  app.kubernetes.io/managed-by: argocd` ở cấp metadata, không có thay đổi nào khác.

- [ ] **Step 5: Commit và PR**

```bash
git add gitops/aiops-engine/
git commit -m "chore(aiops): gỡ label managed-by:argocd dán tay

Label này được dán thủ công khi workload còn deploy bằng kubectl, gây hiểu nhầm
là đã có GitOps quản. Giờ ArgoCD quản thật qua annotation tracking-id nên label
thủ công vừa thừa vừa sai chuẩn.

Chỉ gỡ ở metadata cấp tài nguyên, không đụng pod template — không gây restart."
git push -u origin chore/aiops-remove-fake-managed-by
gh pr create --base main --title "chore(aiops): gỡ label managed-by:argocd dán tay" \
  --body "Follow-up của PR adopt. Label thủ công gây hiểu nhầm; ArgoCD giờ quản thật qua tracking-id. Không đụng pod template nên không restart pod."
```

- [ ] **Step 6: Sau khi merge, xác minh**

```bash
kubectl get deploy aiops-engine -n techx-tf3 -o jsonpath='{.metadata.labels}{"\n"}'
kubectl get pod -n techx-tf3 -l app=aiops-engine \
  -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount
```

Expected: labels chỉ còn `app` và `app.kubernetes.io/name`; tên pod và restartCount không đổi.

---

## Task 7: Cập nhật tài liệu và bàn giao

**Files:**
- Modify: `docs/superpowers/specs/2026-07-28-aiops-engine-gitops-adoption-design.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: kết quả Task 5 và 6
- Produces: hồ sơ khớp thực tế, đầu vào cho plan Phase 2

- [ ] **Step 1: Nhánh mới**

```bash
git fetch origin
git checkout -b docs/aiops-phase1-done origin/main
```

- [ ] **Step 2: Đánh dấu Phase 1 xong trong spec**

Trong mục "Trạng thái" của `docs/superpowers/specs/2026-07-28-aiops-engine-gitops-adoption-design.md`, đổi dòng nói Phase 1–3 chỉ ở mức thiết kế thành: Phase 0 và Phase 1 đã thực thi (kèm ngày và số PR), Phase 2–3 còn ở mức thiết kế.

- [ ] **Step 3: Thêm aiops-engine vào danh sách ArgoCD apps trong `CLAUDE.md`**

Trong mục "Hạ tầng & deploy", dòng liệt kê ArgoCD apps (`techx-corp`, `techx-edge`, `techx-infrastructure-app`, …) — thêm `aiops-engine` vào danh sách, kèm chú thích ngắn là workload AIOps của AIO02, adopt 28/07.

- [ ] **Step 4: Commit và PR**

```bash
git add docs/superpowers/specs/2026-07-28-aiops-engine-gitops-adoption-design.md CLAUDE.md
git commit -m "docs(aiops): đánh dấu Phase 1 hoàn tất, cập nhật danh sách ArgoCD apps"
git push -u origin docs/aiops-phase1-done
gh pr create --base main --title "docs(aiops): Phase 1 hoàn tất" \
  --body "Cập nhật spec và CLAUDE.md sau khi aiops-engine vào ArgoCD."
```

- [ ] **Step 5: Gửi AIO02 4 câu hỏi chặn Phase 2/3**

Lấy từ mục "Việc cần AIO02 xác nhận" trong spec. Ưu tiên câu về access key `AKIA…` của `aio2-admin-team` — nó chặn Phase 2, mà Phase 2 mới là bước đóng thật sự lỗ hổng credential.

- [ ] **Step 6: Dọn worktree**

Dùng tool `ExitWorktree`, hoặc:

```bash
cd /home/tutruong/project/Phase3-TF3-Infra-Sentinel
git worktree remove ../aiops-adoption
```

---

## Sau plan này

Phase 2 (Terraform IRSA + vô hiệu static admin key) và Phase 3 (NetworkPolicy, digest-pin, đồng bộ image CronJob, khôi phục Slack qua cloudflared) làm plan riêng, **sau khi AIO02 trả lời** — cả hai đều chặn bởi câu trả lời của họ.

Riêng việc **vô hiệu access key `AKIA…` của `aio2-admin-team`** là hành động rủi ro cao ngoài cluster: phải xác nhận key không dùng ở CI hay máy cá nhân của AIO02, và luôn đặt `Inactive` (đảo được) trước khi xoá hẳn.
