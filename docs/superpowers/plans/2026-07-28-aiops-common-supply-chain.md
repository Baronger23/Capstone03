# AIOps Common Supply-Chain Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, scan, sign, attest, and promote `aiops-engine` through the common `techx-corp` workflow without losing amd64/arm64 remediation or CronJob training functionality.

**Architecture:** Phase A extends draft PR #544 with a root-source bake target, service-scoped Trivy policy, multi-platform kubectl builder, and standalone AIOps promotion automation while retaining the current external deployment. After Phase A merges, the common workflow creates the verified digest and an atomic Phase B promotion PR that changes both AIOps workloads and removes the obsolete external-image catalogue entries.

**Tech Stack:** Docker Compose/Buildx Bake, GitHub Actions, Trivy v0.72.0, Cosign v2.6.2, CycloneDX, Python 3, pytest, ruamel.yaml, Kubernetes YAML.

## Global Constraints

- Do not replace kubectl shell-outs with the Kubernetes Python client.
- Never ignore `CVE-2026-25681`, `CVE-2026-27136`, `CVE-2026-33814`, or `CVE-2026-39821`.
- The only explicit AIOps ignore entries are `CVE-2026-23949` and `CVE-2026-24049`.
- Full Trivy JSON reports retain all findings; only the blocking AIOps invocation uses `--ignore-unfixed`.
- Preserve existing manifest images and external allowlist entries in Phase A.
- Promotion must update Deployment, CronJob, all three policy branches, and evidence catalogue atomically after attestations exist.
- Build and verify both `linux/amd64` and `linux/arm64`.
- Do not modify flagd/OpenFeature, RBAC, secrets, or live production objects.
- Do not merge, manually dispatch production promotion, sync Argo CD, or mutate live production.

---

### Task 1: Register the root AIOps bake target

**Files:**
- Modify: `phase3 - information/techx-corp-platform/docker-compose.yml`
- Modify: `scripts/ci/test_aiops_image_security_contract.py`
- Modify: `scripts/ci/dockerfile-scope.json`

**Interfaces:**
- Consumes: repository-root `aiops-engine/Dockerfile` and `.dockerignore`.
- Produces: bake target `aiops-engine` tagged `${IMAGE_NAME}:${DEMO_VERSION}-aiops-engine`.

- [ ] **Step 1: Write failing contract tests**

Add assertions equivalent to:

```python
COMPOSE = REPO_ROOT / "phase3 - information/techx-corp-platform/docker-compose.yml"
SCOPE = REPO_ROOT / "scripts/ci/dockerfile-scope.json"

def test_aiops_bake_target_uses_repository_root_context():
    compose = YAML(typ="safe").load(COMPOSE.read_text())
    target = compose["services"]["aiops-engine"]
    assert target["image"] == "${IMAGE_NAME}:${DEMO_VERSION}-aiops-engine"
    assert target["build"]["context"] == "../../aiops-engine"
    assert target["build"]["dockerfile"] == "Dockerfile"

def test_aiops_dockerfile_is_registered_as_multiplatform_production_scope():
    entries = json.loads(SCOPE.read_text())["dockerfiles"]
    assert {
        "path": "aiops-engine/Dockerfile",
        "classification": "production",
        "owner": "aiops-engine",
        "inScope": True,
        "expectedPlatforms": ["linux/amd64", "linux/arm64"],
    } in entries
```

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python3 -m pytest scripts/ci/test_aiops_image_security_contract.py -q
```

Expected: failure because the compose target and scope entry do not exist.

- [ ] **Step 3: Add the minimal compose target and scope entry**

Add:

```yaml
  # AIOps engine
  aiops-engine:
    image: ${IMAGE_NAME}:${DEMO_VERSION}-aiops-engine
    build:
      context: ../../aiops-engine
      dockerfile: Dockerfile
      cache_from:
        - ${IMAGE_NAME}:${IMAGE_VERSION}-aiops-engine
```

Register `aiops-engine/Dockerfile` in `scripts/ci/dockerfile-scope.json` with both expected platforms.

- [ ] **Step 4: Verify compose and bake resolution**

Run from `phase3 - information/techx-corp-platform`:

```bash
docker compose config --quiet
docker buildx bake -f docker-compose.yml aiops-engine --print
```

Expected: both exit 0; bake output resolves the AIOps target with context `../../aiops-engine` and Dockerfile `Dockerfile`.

- [ ] **Step 5: Run contract tests and commit**

```bash
python3 -m pytest scripts/ci/test_aiops_image_security_contract.py -q
git add "phase3 - information/techx-corp-platform/docker-compose.yml" scripts/ci/dockerfile-scope.json scripts/ci/test_aiops_image_security_contract.py
git commit -m "build(aiops): add common bake target"
```

### Task 2: Make kubectl and Trivy policy safe for the common workflow

**Files:**
- Modify: `aiops-engine/Dockerfile`
- Delete: `aiops-engine/.trivyignore`
- Create: `scripts/ci/trivy/aiops-engine.ignore`
- Modify: `.github/workflows/build-push-ecr.yml`
- Modify: `scripts/ci/test_aiops_image_security_contract.py`

**Interfaces:**
- Consumes: BuildKit `BUILDPLATFORM`, `TARGETOS`, and `TARGETARCH`.
- Produces: native kubectl binary for each image platform and a pipeline-owned AIOps gate policy.

- [ ] **Step 1: Extend tests for multi-platform and exact ignore scope**

Add assertions equivalent to:

```python
def test_kubectl_builder_cross_compiles_for_target_platform():
    dockerfile = DOCKERFILE.read_text()
    assert "FROM --platform=$BUILDPLATFORM golang:1.26.5@" in dockerfile
    assert "ARG TARGETOS TARGETARCH" in dockerfile
    assert 'GOOS="$TARGETOS" GOARCH="$TARGETARCH"' in dockerfile
    assert "GOARCH=amd64" not in dockerfile

def test_pipeline_owned_aiops_ignore_contains_only_vendored_cves():
    assert not TRIVYIGNORE.exists()
    assert ignored_cves(PIPELINE_IGNORE) == {
        "CVE-2026-23949",
        "CVE-2026-24049",
    }

def test_common_gate_scopes_ignore_unfixed_to_aiops():
    workflow = COMMON_WORKFLOW.read_text()
    assert workflow.count("scripts/ci/trivy/aiops-engine.ignore") == 2
    assert workflow.count("--ignore-unfixed") == 2
    assert "CVE-2026-25681" not in PIPELINE_IGNORE.read_text()
```

- [ ] **Step 2: Confirm RED**

Run the focused pytest file and confirm failures for hardcoded amd64, old ignore location, and absent workflow policy.

- [ ] **Step 3: Implement target-platform build**

Change the builder header and build arguments to:

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.26.5@sha256:3aff6657219a4d9c14e27fb1d8976c49c29fddb70ba835014f477e1c70636647 AS kubectl-builder
ARG TARGETOS TARGETARCH
...
RUN CGO_ENABLED=0 GOOS="$TARGETOS" GOARCH="$TARGETARCH" \
    go build -mod=readonly -trimpath ...
```

- [ ] **Step 4: Move the two exceptions and wire both gates**

Create `scripts/ci/trivy/aiops-engine.ignore` with the existing evidence comments and only the two vendored CVEs. In both pre-push and post-push blocking scans, construct an empty Bash argument array and populate it only when the service equals `aiops-engine`:

```bash
trivy_policy_args=()
if [ "$SERVICE" = aiops-engine ]; then
  trivy_policy_args+=(
    --ignore-unfixed
    --ignorefile "$GITHUB_WORKSPACE/scripts/ci/trivy/aiops-engine.ignore"
  )
fi
trivy image ... "${trivy_policy_args[@]}" ...
```

Use the loop variable `service` for the post-push equivalent. Do not apply these flags to full JSON evidence scans.

- [ ] **Step 5: Verify and commit**

Run:

```bash
python3 -m pytest scripts/ci/test_aiops_image_security_contract.py scripts/ci/test_workflow_image_bump_contract.py -q
docker buildx build --platform linux/amd64 -f aiops-engine/Dockerfile -t aiops-common:amd64 --load aiops-engine
docker buildx build --platform linux/arm64 -f aiops-engine/Dockerfile -t aiops-common:arm64 --load aiops-engine
```

Inspect each binary with `file` and `kubectl version --client`; then commit the Dockerfile, central policy, workflow, deleted old ignorefile, and tests.

### Task 3: Add an atomic standalone AIOps promotion updater

**Files:**
- Create: `scripts/ci/update-aiops-image-promotion.py`
- Create: `scripts/ci/test_update_aiops_image_promotion.py`
- Modify: `scripts/ci/update-image-overrides.py`

**Interfaces:**
- Consumes: validated `approved-images.json` and exact paths for the two manifests, Kyverno policy, and evidence catalogue.
- Produces: a JSON summary and either a no-op or an atomic four-file AIOps promotion diff.

- [ ] **Step 1: Write failing updater tests**

Cover:

```python
def test_aiops_absent_is_noop(...)
def test_aiops_updates_both_workload_images_to_same_tagged_digest(...)
def test_aiops_aligns_four_cronjob_uid_gid_fields_to_10001(...)
def test_aiops_removes_exactly_six_policy_digest_lines(...)
def test_aiops_removes_exactly_two_evidence_entries(...)
def test_aiops_rejects_wrong_repository_or_malformed_digest(...)
def test_aiops_fails_closed_when_expected_old_entries_are_missing(...)
def test_aiops_preserves_unrelated_policy_and_catalogue_entries(...)
```

The expected image is:

```text
197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/techx-corp:<approved-tag>@sha256:<approved-digest>
```

- [ ] **Step 2: Confirm RED**

Run:

```bash
python3 -m pytest scripts/ci/test_update_aiops_image_promotion.py -q
```

Expected: collection/import failure because the updater does not exist.

- [ ] **Step 3: Implement minimal fail-closed updater**

The script must:

1. load the JSON manifest with duplicate-key rejection;
2. return a no-op summary if `aiops-engine` is absent;
3. validate registry, repository, tag, and digest;
4. require exactly one old `tf-2-ai-engine` image in each workload manifest;
5. require and update exactly four CronJob `: 1000` security identity fields;
6. require and remove exactly six old policy list lines;
7. require and remove exactly two old evidence list entries;
8. parse every resulting YAML document before atomically replacing files;
9. emit a deterministic JSON summary.

Add `aiops-engine` to `ALLOWED_SERVICES` in `update-image-overrides.py`; the workflow will pass it as an excluded standalone service.

- [ ] **Step 4: Run updater tests and existing image-bump tests**

```bash
python3 -m pytest \
  scripts/ci/test_update_aiops_image_promotion.py \
  scripts/ci/test_update_image_overrides.py \
  scripts/ci/test_verify_rendered_images.py -q
```

Expected: all pass with no changes to existing chart-service semantics.

- [ ] **Step 5: Commit**

Commit the standalone updater, its tests, and the one service registration as:

```bash
git commit -m "feat(aiops): automate immutable image promotion"
```

### Task 4: Register AIOps in common workflow scope and image-bump delivery

**Files:**
- Modify: `.github/workflows/build-push-ecr.yml`
- Modify: `scripts/ci/test_workflow_image_bump_contract.py`
- Modify: `scripts/ci/test_aiops_image_security_contract.py`

**Interfaces:**
- Consumes: bake target, central Trivy policy, and standalone promotion updater.
- Produces: scoped AIOps build and a bot promotion PR containing only approved files.

- [ ] **Step 1: Write failing workflow contract tests**

Assert:

```python
assert '"aiops-engine/**"' in workflow
assert "accounting ad aiops-engine cart" in workflow
assert workflow.count('SERVICES="$SERVICES aiops-engine"') == 2
assert '--excluded-service aiops-engine' in workflow
assert "scripts/ci/update-aiops-image-promotion.py" in workflow
```

Also assert the exact-diff and `git add` allowlists include:

```text
gitops/aiops-engine/deployment.yaml
gitops/aiops-engine/cronjob.yaml
gitops/policies/kyverno/allow-approved-external-image-digests.yaml
docs/evidence/mandate-10/external-image-allowlist.yaml
```

- [ ] **Step 2: Confirm RED**

Run both workflow contract suites and observe absent trigger, service registration, scope mapping, and promotion wiring.

- [ ] **Step 3: Register trigger and both scope resolvers**

Add root AIOps and its central policy file to the push/diff path sets. In both duplicated change detectors, map any `aiops-engine/**` or the exact central ignorefile to only `aiops-engine`. Add the service to `ALL_SERVICES`.

- [ ] **Step 4: Wire promotion and verification**

Pass `--excluded-service aiops-engine` to both `update-image-overrides.py` and `verify-rendered-images.py`. Invoke the standalone updater before exact-diff validation. Make exact-diff validation and `git add` derive their allowed path set from whether `EXPECTED_SERVICES` contains `aiops-engine`; retain the current values-only rule otherwise.

The generated PR description must state whether standalone AIOps manifests were updated and must not claim Helm alone verified the AIOps workload.

- [ ] **Step 5: Run workflow tests and actionlint**

```bash
python3 -m pytest \
  scripts/ci/test_aiops_image_security_contract.py \
  scripts/ci/test_workflow_image_bump_contract.py \
  scripts/ci/test_update_aiops_image_promotion.py \
  scripts/ci/test_update_image_overrides.py \
  scripts/ci/test_verify_rendered_images.py -q
actionlint .github/workflows/build-push-ecr.yml
```

- [ ] **Step 6: Commit**

Commit workflow registration and delivery wiring as:

```bash
git commit -m "ci(aiops): join common signed image pipeline"
```

### Task 5: Remove the superseded dedicated workflow

**Files:**
- Delete: `.github/workflows/build-push-aiops.yml`
- Modify: `aiops-engine/README.md`
- Modify: `scripts/ci/test_aiops_image_security_contract.py`

**Interfaces:**
- Consumes: fully registered common workflow.
- Produces: one authoritative AIOps image delivery path.

- [ ] **Step 1: Add failing assertions**

Assert the dedicated workflow and old ignorefile do not exist, and README names `build-push-ecr.yml`, `techx-corp`, post-push scanning, and CycloneDX attestation.

- [ ] **Step 2: Confirm RED**

Run the focused contract before deleting the workflow.

- [ ] **Step 3: Delete and document**

Delete the old workflow, update README supply-chain ownership, and retain the explanation for the patched stable kubectl.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -m pytest scripts/ci/test_aiops_image_security_contract.py scripts/ci/test_workflow_image_bump_contract.py -q
git commit -m "ci(aiops): remove dedicated image workflow"
```

### Task 6: Prove context filtering and end-to-end candidate behavior

**Files:**
- Temporarily create then delete: `aiops-engine/models/codex-context-sentinel.joblib`
- Temporarily create then delete: `aiops-engine/scratch/codex-context-sentinel.txt`
- No committed production-file changes expected.

**Interfaces:**
- Consumes: final bake target and `.dockerignore`.
- Produces: verification evidence only.

- [ ] **Step 1: Add temporary sentinels**

Create one small text sentinel under each excluded directory using `apply_patch`.

- [ ] **Step 2: Build through the exact bake target**

From the platform directory:

```bash
IMAGE_NAME=aiops-context-check IMAGE_VERSION=verify DEMO_VERSION=verify \
docker buildx bake -f docker-compose.yml aiops-engine \
  --set aiops-engine.platform=linux/amd64 \
  --set aiops-engine.output=type=docker
```

- [ ] **Step 3: Inspect filtering and runtime**

Verify:

```bash
docker run --rm --entrypoint sh aiops-context-check:verify-aiops-engine -c \
  'test ! -e /app/scratch/codex-context-sentinel.txt &&
   test ! -e /app/models/codex-context-sentinel.joblib &&
   ! find /app -name "*.joblib" -print -quit | grep -q .'
docker run --rm --entrypoint python aiops-context-check:verify-aiops-engine -c \
  'import main; print(main.app.title)'
```

Run the exact blocking Trivy policy and `govulncheck -mode=binary` against the shipped kubectl.

- [ ] **Step 4: Verify arm64 binary architecture**

Build/export the arm64 target and use `file` on the extracted kubectl. Expected: `ARM aarch64`; amd64 candidate must report `x86-64`.

- [ ] **Step 5: Remove sentinels and run final suites**

Delete both temporary sentinel files, verify they are absent from `git status`, then run:

```bash
python3 -m pytest scripts/ci -q
git diff --check
docker compose -f "phase3 - information/techx-corp-platform/docker-compose.yml" config --quiet
```

Record pre-existing unrelated failures separately; do not suppress or skip new failures.

### Task 7: Review and update draft PR #544

**Files:**
- Review every file changed from `origin/main...HEAD`.
- Update: PR #544 title/body if necessary.

**Interfaces:**
- Consumes: verified Phase A commits.
- Produces: a reviewable draft PR that causes no production rollout before merge.

- [ ] **Step 1: Rebase or merge latest `origin/main` safely**

Fetch, confirm the worktree is clean, and use a non-destructive fast-forward/rebase strategy. Do not overwrite concurrent user changes.

- [ ] **Step 2: Run five-axis review and final verification**

Review correctness, readability, architecture, security, and performance. Confirm Phase A retains both old manifest images and all external allowlist entries.

- [ ] **Step 3: Push and monitor checks**

Push the existing branch, update draft PR #544 with the two-phase rollout explanation and verification evidence, then monitor all checks to terminal status.

- [ ] **Step 4: Stop at the merge gate**

Do not mark ready, merge, manually dispatch the production workflow, alter the cluster, or sync Argo CD without explicit user approval.
