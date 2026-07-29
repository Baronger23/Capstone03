# ARM NodePool Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tăng ARM Spot lên tối đa 4 node `c/m` và bổ sung ARM On-Demand cold fallback tối đa 2 node mà chưa chuyển thêm service sang ARM.

**Architecture:** Giữ hai NodePool ARM độc lập nhưng dùng cùng scheduling contract `techx.io/workload=elastic` và `techx.io/arch=arm64`. Spot có weight `100`; On-Demand fallback có weight `10`, NodeClass/tag riêng và không có desired/min node nên steady state là 0.

**Tech Stack:** Karpenter `karpenter.sh/v1`, AWS provider `karpenter.k8s.aws/v1`, YAML, PyYAML, pytest, Argo CD directory source.

## Global Constraints

- Chỉ thay capacity foundation trong PR này; không chuyển service sang ARM.
- Giữ nguyên AMD Spot cap 2 và AMD On-Demand fallback cap 2.
- Không thay HPA, resources, topology spread, managed nodegroup hoặc application code.
- Không thay đổi `flagd`, OpenFeature, `/flagservice` hoặc `envoy.filters.http.fault`.
- ARM Spot: `arm64`, Spot, weight `100`, category `c/m`, CPU `2/4`, generation `>2`, memory `>3072Mi`, cap `4 nodes / 16 CPU / 64Gi`.
- ARM On-Demand fallback: `arm64`, On-Demand, weight `10`, category `c/m`, CPU `2/4`, generation `>2`, memory `>3072Mi`, cap `2 nodes / 8 CPU / 32Gi`.
- Giữ AMI ARM AL2023 đã pin: `ami-038711df7b713297d`.
- Production mutation chỉ qua merge PR và Argo CD; các bước trước merge chỉ được read-only hoặc server dry-run.
- Thiết kế nguồn: `docs/superpowers/specs/2026-07-29-arm-nodepool-foundation-design.md`.

---

## File Map

- Create `scripts/ci/test_arm_nodepool_contract.py`: contract test cho ARM Spot, ARM fallback và scope guard AMD.
- Modify `gitops/karpenter/spot-nodepool.yaml`: thu hẹp ARM Spot về `c/m`, nâng cap lên 4 node.
- Modify `gitops/karpenter/ondemand-fallback-nodepool.yaml`: thêm ARM On-Demand NodePool và EC2NodeClass riêng.
- Existing `.github/workflows/build-push-ecr.yml` and `.github/workflows/test-image-bump.yml`: không sửa; cả hai đã collect/run toàn bộ `scripts/ci`.

### Task 1: ARM Spot contract và cap

**Files:**

- Create: `scripts/ci/test_arm_nodepool_contract.py`
- Modify: `gitops/karpenter/spot-nodepool.yaml:77-154`

**Interfaces:**

- Consumes: multi-document YAML trong `gitops/karpenter/spot-nodepool.yaml`.
- Produces: helper `resource(path: Path, kind: str, name: str) -> dict` và `requirements(nodepool: dict) -> dict[str, dict]` để Task 2 tái sử dụng.

- [ ] **Step 1: Viết contract test cho ARM Spot**

Tạo `scripts/ci/test_arm_nodepool_contract.py`:

```python
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[2]
SPOT = REPO / "gitops/karpenter/spot-nodepool.yaml"
FALLBACK = REPO / "gitops/karpenter/ondemand-fallback-nodepool.yaml"


def documents(path: Path) -> list[dict]:
    return [
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if document
    ]


def resource(path: Path, kind: str, name: str) -> dict:
    for document in documents(path):
        if document["kind"] == kind and document["metadata"]["name"] == name:
            return document
    raise AssertionError(f"{kind}/{name} not found in {path}")


def requirements(nodepool: dict) -> dict[str, dict]:
    return {
        requirement["key"]: requirement
        for requirement in nodepool["spec"]["template"]["spec"]["requirements"]
    }


def test_arm_spot_uses_c_m_with_bounded_four_node_capacity():
    nodepool = resource(SPOT, "NodePool", "flash-sale-spot-arm64")
    requirement = requirements(nodepool)

    assert nodepool["spec"]["weight"] == 100
    assert requirement["kubernetes.io/arch"]["values"] == ["arm64"]
    assert requirement["karpenter.sh/capacity-type"]["values"] == ["spot"]
    assert requirement["karpenter.k8s.aws/instance-category"]["values"] == [
        "c",
        "m",
    ]
    assert requirement["karpenter.k8s.aws/instance-cpu"]["values"] == ["2", "4"]
    assert nodepool["spec"]["limits"] == {
        "cpu": "16",
        "memory": "64Gi",
        "nodes": 4,
    }


def test_existing_amd_spot_cap_stays_at_two_nodes():
    nodepool = resource(SPOT, "NodePool", "flash-sale-spot")
    requirement = requirements(nodepool)

    assert requirement["kubernetes.io/arch"]["values"] == ["amd64"]
    assert requirement["karpenter.sh/capacity-type"]["values"] == ["spot"]
    assert nodepool["spec"]["limits"]["nodes"] == 2
```

- [ ] **Step 2: Chạy test và xác nhận RED**

Run:

```bash
python -m pytest -q scripts/ci/test_arm_nodepool_contract.py
```

Expected: `test_arm_spot_uses_c_m_with_bounded_four_node_capacity` FAIL vì manifest cũ còn category `["c", "m", "r", "t"]` và cap 2; test AMD pass.

- [ ] **Step 3: Sửa ARM Spot tối thiểu**

Trong `NodePool/flash-sale-spot-arm64`, thay đúng hai block:

```yaml
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m"]
```

```yaml
  limits:
    cpu: "16"
    memory: 64Gi
    nodes: 4
```

Không sửa `NodePool/flash-sale-spot`, EC2NodeClass, taints, labels, disruption hoặc AMI.

- [ ] **Step 4: Chạy targeted test và xác nhận GREEN**

Run:

```bash
python -m pytest -q scripts/ci/test_arm_nodepool_contract.py
```

Expected: `2 passed`.

- [ ] **Step 5: Kiểm tra diff đúng phạm vi Task 1**

Run:

```bash
git diff --check
git diff -- scripts/ci/test_arm_nodepool_contract.py gitops/karpenter/spot-nodepool.yaml
```

Expected: chỉ có test mới và hai thay đổi ARM Spot đã nêu.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/ci/test_arm_nodepool_contract.py gitops/karpenter/spot-nodepool.yaml
git commit -m "feat: expand bounded ARM spot capacity"
```

### Task 2: ARM On-Demand cold fallback

**Files:**

- Modify: `scripts/ci/test_arm_nodepool_contract.py`
- Modify: `gitops/karpenter/ondemand-fallback-nodepool.yaml:58-end`

**Interfaces:**

- Consumes: `resource()` và `requirements()` từ Task 1.
- Produces: `NodePool/elastic-ondemand-fallback-arm64` và `EC2NodeClass/elastic-ondemand-fallback-arm64`.

- [ ] **Step 1: Thêm failing tests cho ARM fallback và AMD scope guard**

Nối vào `scripts/ci/test_arm_nodepool_contract.py`:

```python
def taints(nodepool: dict) -> dict[str, dict]:
    return {
        taint["key"]: taint
        for taint in nodepool["spec"]["template"]["spec"]["taints"]
    }


def test_arm_ondemand_fallback_matches_arm_scheduling_contract():
    nodepool = resource(
        FALLBACK, "NodePool", "elastic-ondemand-fallback-arm64"
    )
    requirement = requirements(nodepool)
    taint = taints(nodepool)

    assert nodepool["spec"]["weight"] == 10
    assert nodepool["spec"]["template"]["metadata"]["labels"] == {
        "techx.io/capacity": "on-demand-fallback",
        "techx.io/workload": "elastic",
        "techx.io/arch": "arm64",
    }
    assert taint["techx.io/workload"] == {
        "key": "techx.io/workload",
        "value": "elastic",
        "effect": "NoSchedule",
    }
    assert taint["techx.io/arch"] == {
        "key": "techx.io/arch",
        "value": "arm64",
        "effect": "NoSchedule",
    }
    assert requirement["kubernetes.io/arch"]["values"] == ["arm64"]
    assert requirement["karpenter.sh/capacity-type"]["values"] == ["on-demand"]
    assert requirement["karpenter.k8s.aws/instance-category"]["values"] == [
        "c",
        "m",
    ]
    assert requirement["karpenter.k8s.aws/instance-cpu"]["values"] == ["2", "4"]
    assert nodepool["spec"]["template"]["spec"]["nodeClassRef"]["name"] == (
        "elastic-ondemand-fallback-arm64"
    )
    assert nodepool["spec"]["limits"] == {
        "cpu": "8",
        "memory": "32Gi",
        "nodes": 2,
    }
    assert nodepool["spec"]["disruption"] == {
        "consolidationPolicy": "WhenEmptyOrUnderutilized",
        "consolidateAfter": "10m",
        "budgets": [{"nodes": "0", "reasons": ["Drifted"]}],
    }


def test_arm_fallback_uses_dedicated_pinned_arm_nodeclass():
    nodeclass = resource(
        FALLBACK, "EC2NodeClass", "elastic-ondemand-fallback-arm64"
    )

    assert nodeclass["spec"]["amiFamily"] == "AL2023"
    assert nodeclass["spec"]["amiSelectorTerms"] == [
        {"id": "ami-038711df7b713297d"}
    ]
    assert nodeclass["spec"]["tags"]["techx.io/capacity"] == (
        "on-demand-fallback"
    )
    assert nodeclass["spec"]["tags"]["techx.io/arch"] == "arm64"


def test_existing_amd_fallback_cap_stays_at_two_nodes():
    nodepool = resource(FALLBACK, "NodePool", "elastic-ondemand-fallback")
    requirement = requirements(nodepool)

    assert requirement["kubernetes.io/arch"]["values"] == ["amd64"]
    assert requirement["karpenter.sh/capacity-type"]["values"] == ["on-demand"]
    assert nodepool["spec"]["limits"]["nodes"] == 2
```

- [ ] **Step 2: Chạy test và xác nhận RED**

Run:

```bash
python -m pytest -q scripts/ci/test_arm_nodepool_contract.py
```

Expected: hai ARM fallback tests FAIL với
`NodePool/elastic-ondemand-fallback-arm64 not found`; AMD guards và ARM Spot test pass.

- [ ] **Step 3: Thêm ARM On-Demand NodePool và EC2NodeClass**

Nối sau `EC2NodeClass/elastic-ondemand-fallback` trong
`gitops/karpenter/ondemand-fallback-nodepool.yaml`:

```yaml
---
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: elastic-ondemand-fallback-arm64
spec:
  weight: 10
  template:
    metadata:
      labels:
        techx.io/capacity: on-demand-fallback
        techx.io/workload: elastic
        techx.io/arch: arm64
    spec:
      taints:
        - key: techx.io/workload
          value: elastic
          effect: NoSchedule
        - key: techx.io/arch
          value: arm64
          effect: NoSchedule
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: ["arm64"]
        - key: kubernetes.io/os
          operator: In
          values: ["linux"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m"]
        - key: karpenter.k8s.aws/instance-generation
          operator: Gt
          values: ["2"]
        - key: karpenter.k8s.aws/instance-cpu
          operator: In
          values: ["2", "4"]
        - key: karpenter.k8s.aws/instance-memory
          operator: Gt
          values: ["3072"]
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: elastic-ondemand-fallback-arm64
      expireAfter: 168h
      terminationGracePeriod: 10m
  limits:
    cpu: "8"
    memory: 32Gi
    nodes: 2
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 10m
    budgets:
      - nodes: "0"
        reasons:
          - Drifted
---
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: elastic-ondemand-fallback-arm64
spec:
  role: KarpenterNodeRole-techx-corp-tf3
  amiFamily: AL2023
  associatePublicIPAddress: false
  amiSelectorTerms:
    - id: ami-038711df7b713297d
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: techx-corp-tf3
        kubernetes.io/role/internal-elb: "1"
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: techx-corp-tf3
  tags:
    karpenter.sh/discovery: techx-corp-tf3
    techx.io/mandate: "13"
    techx.io/capacity: on-demand-fallback
    techx.io/arch: arm64
```

Không sửa hai resource AMD đã có trong file.

- [ ] **Step 4: Chạy targeted test và xác nhận GREEN**

Run:

```bash
python -m pytest -q scripts/ci/test_arm_nodepool_contract.py
```

Expected: `5 passed`.

- [ ] **Step 5: Kiểm tra YAML inventory**

Run:

```bash
yq eval-all 'select(.kind == "NodePool") | .metadata.name' \
  gitops/karpenter/*.yaml
yq eval-all 'select(.kind == "EC2NodeClass") | .metadata.name' \
  gitops/karpenter/*.yaml
```

Expected NodePools:

```text
elastic-ondemand-fallback
elastic-ondemand-fallback-arm64
flash-sale-spot
flash-sale-spot-arm64
```

Expected EC2NodeClasses:

```text
elastic-ondemand-fallback
elastic-ondemand-fallback-arm64
flash-sale-spot
flash-sale-spot-arm64
```

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts/ci/test_arm_nodepool_contract.py \
  gitops/karpenter/ondemand-fallback-nodepool.yaml
git commit -m "feat: add ARM on-demand fallback"
```

### Task 3: Full verification và PR readiness

**Files:**

- Verify only; không tạo hoặc sửa file.

**Interfaces:**

- Consumes: hai commit implementation từ Task 1–2.
- Produces: evidence local/server dry-run để mở PR; không mutation production.

- [ ] **Step 1: Chạy targeted contract**

Run:

```bash
python -m pytest -q scripts/ci/test_arm_nodepool_contract.py
```

Expected: `5 passed`.

- [ ] **Step 2: Chạy CI Python suite giống workflow**

Run:

```bash
python -m pytest --collect-only -q scripts/ci
python -m pytest -q scripts/ci
```

Expected: collection và toàn bộ suite pass; không error/warning mới do thay đổi này.

- [ ] **Step 3: Kiểm tra identity và tunnel trước server dry-run**

Run:

```bash
aws sts get-caller-identity --profile default --output json
curl -ks --max-time 3 https://localhost:8443/readyz
```

Expected:

- account `197826770971`;
- principal `cdo-admin-team`;
- `/readyz` trả `ok`.

Nếu tunnel không sẵn sàng, khôi phục tunnel bằng procedure hiện có trước khi
tiếp tục; không coi lỗi `localhost:8443 refused` là cluster outage.

- [ ] **Step 4: Chạy Kubernetes server dry-run**

Run:

```bash
kubectl apply --dry-run=server -f gitops/karpenter
```

Expected:

- 4 NodePool và 4 EC2NodeClass được API server chấp nhận;
- output chỉ có `(server dry run)`;
- không object nào được persist.

- [ ] **Step 5: Kiểm tra diff scope và whitespace**

Run:

```bash
git diff --check origin/main...HEAD
git diff --name-only origin/main...HEAD
git status --short --branch
```

Expected changed files:

```text
docs/superpowers/plans/2026-07-29-arm-nodepool-foundation.md
docs/superpowers/specs/2026-07-29-arm-nodepool-foundation-design.md
gitops/karpenter/ondemand-fallback-nodepool.yaml
gitops/karpenter/spot-nodepool.yaml
scripts/ci/test_arm_nodepool_contract.py
```

Expected worktree clean; không có `AGENTS.md`, `.codex/`, `.agents/`,
`.claude/`, `CLAUDE.md`, `CLAUDE.local.md`, values/service manifest hoặc
protected flag/fault path trong diff.

- [ ] **Step 6: Review PR readiness**

Xác nhận trong PR description:

- thay đổi chỉ là capacity maximum, không phải desired count;
- chưa migrate service;
- ARM fallback steady-state phải là 0;
- risk: ARM Spot NodePool requirement change có thể tạo Drift;
- rollback bằng revert PR qua GitOps;
- post-merge gates: Argo `Synced/Healthy`, cả hai ARM NodePool Ready,
  `product-catalog` 2/2, không Pending/churn bất thường.

Không merge hoặc sync production trong task này; chờ reviewer/user merge.
