# Runbook — Deploy Shopping Copilot (AIO02 service, TF3-compliant path)

**Owner:** CDO02 (platform wiring) · **Service owner:** AIO02
**Source of truth for the app:** `shopping-copilot/contracts/DEPLOYMENT-SPEC.md` (v1.0.0)

This runbook deploys the `shopping-copilot` chatbot the TF3 way: GitOps/ArgoCD, image through
the supply-chain gate (Trivy + Cosign, digest-pinned), IRSA for Bedrock, secrets via
ExternalSecret (nothing secret in git), private exposure via Cloudflare Access.

It intentionally does **not** use AIO02's `shopping-copilot/contracts/k8s-*.yaml` manifests —
those were written against the pre–Mandate-#8 world and would (a) point at the turned-off
in-cluster `postgresql`/`valkey-cart` and (b) commit `DB_PASSWORD: otelp` to a tracked file
(disqualify-level). The compliant equivalents live in `gitops/shopping-copilot/`.

---

## What this PR adds

| Layer | File(s) |
|---|---|
| IRSA role (Bedrock/Guardrail/KB/S3, least-privilege) | `infra/modules/eks-platform/shopping-copilot-bedrock.tf` |
| ECR repo (immutable + scan + lifecycle) | `infra/live/production/ecr-shopping-copilot.tf` |
| Private SSO route `copilot.arthur-ngo.org` | `infra/live/production/cloudflare-access.tf` (added `copilot` route) |
| Gated image build | `.github/workflows/build-push-copilot.yml` |
| Workload manifests | `gitops/shopping-copilot/{serviceaccount,configmap,deployment,service,pdb}.yaml` |
| ArgoCD app | `gitops/apps/shopping-copilot-app.yaml` |
| Valkey URL secret (rediss://) | `gitops/secrets/shopping-copilot-secrets.yaml` |

---

## Prerequisites / dependencies

1. **App source must be present.** The build workflow builds `shopping-copilot/Dockerfile`.
   The source arrives via AIO02's PR (#468, branch `feature/shopping-copilot`). Either land
   that source on `main` first, or dispatch the build workflow against a ref that contains it.
2. **RDS reachable from copilot pod.** Copilot joins the same node SG egress that
   product-reviews already uses to reach RDS — no SG change expected. Verify anyway (step 6).
3. `enable_cloudflare_access = true` already set in production tfvars (it is — REL-17 live).

---

## Deploy sequence

### 1. Terraform (IRSA + ECR + Cloudflare route)
```sh
export AWS_PROFILE=techx-new
cd infra/live/production
# ECR repo very likely pre-exists (AIO02 pushed images) - import before apply or it fails:
terraform import aws_ecr_repository.shopping_copilot shopping-copilot   # skip if already in state
terraform plan -out=tfplan
terraform apply tfplan
```
Confirm the plan only adds: the IRSA role+policy, ECR lifecycle, and the `copilot` Cloudflare
Access app + DNS + tunnel ingress rule. Nothing else should change.

Role ARN produced (deterministic, already wired into the SA manifest):
`arn:aws:iam::197826770971:role/techx-corp-tf3-shopping-copilot-bedrock`

### 2. Build the image through the gate
Run **Actions → “Build & Push Shopping Copilot image” → Run workflow** (from `main`).
It builds `linux/amd64`, runs the blocking Trivy HIGH/CRITICAL gate, pushes by digest, and
Cosign-keyless-signs the digest. Copy the `image_digest` from the run summary.

### 3. Pin the digest
Replace `sha256:REPLACE_WITH_CI_DIGEST` in `gitops/shopping-copilot/deployment.yaml` with the
digest from step 2. Commit + merge. (Until this is a real digest the pod stays
ImagePullBackOff — harmless to everything else.)

### 4. Let ArgoCD sync
`techx-corp-bootstrap` picks up `gitops/apps/shopping-copilot-app.yaml`; the new `shopping-copilot`
Application syncs `gitops/shopping-copilot/`. The `shopping-copilot-valkey-url` ExternalSecret
is synced by the existing `flagd-secret-sync` app (it watches `gitops/secrets`).

### 5. Verify (via SSM tunnel or kubectl.arthur-ngo.org)
```sh
kubectl -n techx-tf3 get deploy shopping-copilot
kubectl -n techx-tf3 get pods -l app=shopping-copilot -o wide      # 2/2, spread across nodes/AZs
kubectl -n techx-tf3 get externalsecret shopping-copilot-valkey-url  # SecretSynced=True
kubectl -n techx-tf3 exec deploy/shopping-copilot -- \
  wget -qO- localhost:8001/health                                   # {"status":"ok",...}
```

### 6. Smoke the dependencies from inside the pod
- **RDS:** a `/api/chat` product-search query returns catalog results (SQL path works).
- **Bedrock:** reply is generated (IRSA working; `copilot_bedrock_calls_total` increments).
- **Valkey:** a follow-up message in the same session remembers context (session persistence).
  If context is lost every turn → the Redis client isn't doing TLS/auth (see Open Items).

### 7. Access
Browse `https://copilot.arthur-ngo.org/chatbot` — Cloudflare Access SSO gates it (same
allowlist as grafana/argocd). No public storefront exposure.

---

## Open items / AIO02 dependencies (verify before calling it done)

1. **Valkey TLS/auth in the app.** The copilot was built against plaintext in-cluster Valkey.
   `VALKEY_URL` is now `rediss://` (TLS) with an AUTH token. Confirm the client honours both,
   and that logical DB index `/1` is valid on our ElastiCache (unsupported if cluster-mode).
   Fallback per spec: session degrades to in-memory — functional but no HA persistence.
2. **RAG Knowledge Base health.** `BEDROCK_KB_ID=UCTITOWFHE` backs onto a vector store.
   OpenSearch Serverless was turned off for cost (cost-breakdown §2). If the KB's store is
   gone, RAG Flow-2 fails and search degrades to SQL-only. Confirm the KB is live, or accept
   SQL-only and note it.
3. **Bedrock model/guardrail/KB ARNs.** The IRSA policy is scoped to the IDs in the spec. If
   AIO02 promotes the guardrail out of `DRAFT` or moves the KB/model, update the locals in
   `shopping-copilot-bedrock.tf`.
4. **DB user path.** We inject `DB_CONNECTION_STRING` (RDS managed creds). If the app builds
   its own connection from `DB_USER`/`DB_PASSWORD` instead, it will fail — it must read
   `DB_CONNECTION_STRING` (same contract product-reviews uses).
5. **NetworkPolicy.** Deliberately NOT added here — the Mandate #5 batch caused the 20/07
   outage and is being rebuilt by CDO01. Add copilot egress (RDS/ElastiCache/Bedrock/gRPC)
   when that work lands, tested on VPC CNI.

## Rollback
`gitops/apps/shopping-copilot-app.yaml` removal (or `kubectl -n argocd delete app shopping-copilot`
after disabling auto-sync) tears the service down cleanly. It shares no datastore writer path
with any other service, so removal is isolated — nothing else depends on it.
