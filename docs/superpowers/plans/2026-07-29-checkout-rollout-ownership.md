# Checkout Rollout Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop Argo CD from declaring replicas for the checkout source Deployment while keeping the HPA-owned `checkout-rollout` at a two-replica minimum.

**Architecture:** The checkout Deployment remains the `workloadRef` pod-template source, but its replica field is omitted by the existing chart switch. The Rollout already omits its replica field; `checkout-hpa` owns the Rollout scale subresource and the existing Argo ignore rules preserve both controller boundaries.

**Tech Stack:** Helm, Kubernetes/Argo Rollouts manifests, Pytest, PyYAML.

## Global Constraints

- Do not migrate checkout to ARM in this change.
- Do not modify Envoy, flagd, `/flagservice`, fault injection, checkout application code, MSK configuration, HPA thresholds, or AnalysisTemplate queries.
- Do not scale production until this PR is merged, Argo CD is Synced/Healthy at the merge revision, and the user explicitly authorizes the one-time scale action.

---

### Task 1: Transfer checkout Deployment replica ownership

**Files:**
- Create: `scripts/ci/test_checkout_rollout_ownership_contract.py`
- Modify: `phase3 - information/deploy/values-prod.yaml`

**Interfaces:**
- Consumes: the exact Helm value-file order declared by `gitops/apps/techx-corp.yaml`.
- Produces: rendered checkout Deployment and Rollout objects without `spec.replicas`; the HPA keeps a two-replica Rollout minimum and progressive source scale-down remains enabled.

- [ ] **Step 1: Write the failing render contract**

Create a test that renders the chart with the production value files and asserts:

```python
deployment = named_document(documents, "Deployment", "checkout")
rollout = named_document(documents, "Rollout", "checkout-rollout")

assert "replicas" not in deployment["spec"]
assert "replicas" not in rollout["spec"]
assert rollout["spec"]["workloadRef"] == {
    "apiVersion": "apps/v1",
    "kind": "Deployment",
    "name": "checkout",
    "scaleDown": "progressively",
}
```

The same test must parse `gitops/infrastructure/hpa-hotpath.yaml` and
`gitops/apps/techx-corp.yaml` to assert that `checkout-hpa` targets
`checkout-rollout` with `minReplicas: 2` and `maxReplicas: 8`, and that Argo CD
still ignores `/spec/replicas` for both checkout controllers.

- [ ] **Step 2: Run the contract and verify RED**

Run:

```bash
python3 -m pytest scripts/ci/test_checkout_rollout_ownership_contract.py -q
```

Expected: FAIL because the rendered checkout Deployment currently contains
`spec.replicas: 2`.

- [ ] **Step 3: Apply the minimal production-values change**

Under `components.checkout` in
`phase3 - information/deploy/values-prod.yaml`, add:

```yaml
replicasManagedExternally: true
```

Keep `replicas: 2` as the documented component baseline. The live Rollout
replica count remains HPA-owned through
`rollouts.checkout.replicasManagedExternally: true`.

- [ ] **Step 4: Run the contract and verify GREEN**

Run:

```bash
python3 -m pytest scripts/ci/test_checkout_rollout_ownership_contract.py -q
```

Expected: PASS.

- [ ] **Step 5: Verify the exact production render**

Run Helm dependency build, lint, and template with the value-file order from
`gitops/apps/techx-corp.yaml`. Confirm the rendered checkout Deployment omits
`spec.replicas`, the checkout Rollout also omits `spec.replicas`, and image,
probes, resources, scheduling, environment, service account, and pod template
remain unchanged.

- [ ] **Step 6: Run repository verification**

Run:

```bash
git diff --check
/tmp/checkout-ownership-venv/bin/python -m pytest scripts/ci -q -rs
```

Expected: all tests pass; only environment-conditional tests may be skipped.

- [ ] **Step 7: Review and commit**

Review the two-file implementation diff for correctness, security,
architecture, and performance, then commit:

```bash
git add \
  "phase3 - information/deploy/values-prod.yaml" \
  scripts/ci/test_checkout_rollout_ownership_contract.py
git commit -m "fix: transfer checkout replicas to rollout"
```

- [ ] **Step 8: Open the PR and stop before production scaling**

Push `fix/checkout-rollout-ownership`, open a ready PR, and wait for all checks.
The PR description must state that post-merge verification and the explicitly
approved one-time Deployment scale are still required.
