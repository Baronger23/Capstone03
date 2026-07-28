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

### 3b. Create the confirmation-secret out of band (one-time, never in git)
The write-confirmation HMAC key. Without it the app uses a predictable hardcoded default and
add-to-cart confirm tokens become forgeable. Same out-of-band pattern as the flagd/cloudflared
tokens (a random value, created directly in the cluster):
```sh
export AWS_PROFILE=techx-new
kubectl -n techx-tf3 create secret generic shopping-copilot-confirmation \
  --from-literal=secret="$(openssl rand -hex 32)"
```
Rotate by recreating the secret and restarting the deployment. (The DB and Valkey secrets are
handled automatically by ExternalSecrets — only this one is manual, because there is no
upstream source for it.)

### 4. Let ArgoCD sync
`techx-corp-bootstrap` picks up `gitops/apps/shopping-copilot-app.yaml`; the new `shopping-copilot`
Application syncs `gitops/shopping-copilot/`. The `shopping-copilot-valkey-url` and
`shopping-copilot-db` ExternalSecrets are synced by the existing `flagd-secret-sync` app (it
watches `gitops/secrets`).

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

## Source-code findings (reviewing AIO02 PR #468) and how this deploy handles them

Resolved on our side — no AIO02 change needed:
- **DB creds** — `src/database/connect.py` reads `DB_USER`/`DB_PASSWORD`/`DB_SSLMODE`
  **individually** (defaults `otelu`/`otelp`/`prefer`); it does NOT read a DSN. So we inject
  RDS-managed master creds as discrete `DB_USER`/`DB_PASSWORD` (ExternalSecret
  `shopping-copilot-db`) + `DB_SSLMODE=require`. Do NOT rely on `DB_CONNECTION_STRING` — the
  app ignores it.
- **Valkey** — verified 2026-07-27: ElastiCache `techx-tf3-valkey` is `ClusterEnabled=false`,
  TLS on, Auth on → `redis.Redis.from_url("rediss://…:6379/1")` (what the app uses) works with
  TLS+auth and the `/1` index. If Valkey is unreachable the app falls back to a per-replica
  file under `/app/data` (emptyDir) — sessions stop being shared, so Valkey is the real store.
- **runAsUser** — image `appuser` is UID 1000 and owns `/app`; the app writes
  `uvicorn_execution.txt` (CWD) and `/app/data` at startup, so the pod runs as 1000 (a
  mismatched UID crashes it on import).
- **gRPC ports** — the app's `service_config.py` defaults (3550/7070/9090/7001/50051) are the
  vanilla OTel-demo ports and are WRONG for our chart (`:8080`, reviews `:3551`). We override
  all six `*_ADDR` in the ConfigMap with the correct cluster ports.

Confirmed / fixed on our side (2026-07-27):
- **RDS schema** — `product-catalog/main.go` queries `FROM catalog.products` and
  `product-reviews/database.py` queries `FROM reviews.productreviews`. Both services run live
  on RDS `otel` using the same RDS-managed master creds we inject into the copilot, so those
  schemas exist and the master user can read them. The copilot's SQL tools hit the same tables.
- **RAG Knowledge Base — ALIVE, region corrected.** `UCTITOWFHE` (techx-products-kb-v2) is
  ACTIVE in **us-east-1**, not ap-southeast-1 as the spec implied. The app's `kb_client` reads
  `BEDROCK_KB_REGION` (default us-east-1); we pin it explicitly and scope the IRSA `bedrock:Retrieve`
  to the us-east-1 KB ARN. RAG Flow-2 works. (An orphan KB `VGXRPNYPPA` in DELETE_UNSUCCESSFUL
  is unrelated — a cost-cleanup item.)
- **Write-confirmation HMAC key** — `confirmation.py` defaults to a predictable literal if
  `COPILOT_CONFIRMATION_SECRET` is unset (forgeable add-to-cart tokens). We inject it from the
  out-of-band `shopping-copilot-confirmation` secret (step 3b), so the default is never used.
- **DB password default** — `connect.py` hardcodes `otelp` as the `DB_PASSWORD` fallback (dead
  self-hosted cred); we always set `DB_PASSWORD` from the RDS secret, so the fallback is never hit.

Still to confirm / accept — do not block a first deploy (hardening, need app code):
1. **`/metrics` not implemented.** No `/metrics` route/prometheus client despite spec §7.4.
   Scrape annotation removed; SLO/alert claims are unbacked until AIO02 adds it. (Cannot be
   synthesized from the platform side — the `copilot_*` counters are internal to the app.)
2. **Debug endpoints — blocked at the edge (our side).** `/debug/*` (dumps all users'
   sessions/cache) and `/docs` (Swagger) are unauthenticated in the app. We hard-block them at
   the tunnel: `blocked_paths` in `cloudflare-access.tf` makes cloudflared return 404 for
   `^/(debug|docs)` on `copilot.arthur-ngo.org` before the request reaches the pod, even for
   SSO users. In-cluster direct access to `shopping-copilot:8001/debug` is still open (same
   trust boundary as every other Service; NetworkPolicy is the tool, deferred). Full in-app
   disable (an `ENABLE_DEBUG=false` flag) remains an AIO02 hardening ask.
3. **Bedrock ARNs.** IRSA scoped to the contract's model/guardrail/KB IDs; if AIO02 promotes
   the guardrail out of `DRAFT` or moves the KB/model, update the locals in
   `shopping-copilot-bedrock.tf`.
4. **NetworkPolicy.** Deliberately NOT added (Mandate #5 batch caused the 20/07 outage; CDO01
   is rebuilding it). Add copilot egress (RDS/ElastiCache/Bedrock/gRPC) when that lands.

## Rollback
`gitops/apps/shopping-copilot-app.yaml` removal (or `kubectl -n argocd delete app shopping-copilot`
after disabling auto-sync) tears the service down cleanly. It shares no datastore writer path
with any other service, so removal is isolated — nothing else depends on it.
