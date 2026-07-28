# ADR 0015 — Deploy Shopping Copilot the TF3-compliant way (CDO02)

- **Status:** Accepted
- **Date:** 2026-07-27
- **Deciders:** CDO02 (platform), with AIO02 (service owner)
- **Related:** Mandate #14 (AI eval standard), Mandate #8 (managed datastores), Mandate #1
  (network least-exposure), PM-101 (image supply-chain gate), REL-17 (Cloudflare Access)

## Context

AIO02 delivered `shopping-copilot` (FastAPI conversational shopping assistant on Bedrock Nova
Lite) with a `DEPLOYMENT-SPEC.md` and ready-to-`kubectl-apply` manifests. Reviewed against the
current platform, the handed-over manifests could not be applied as-is:

1. They point the app at the in-cluster `postgresql`/`valkey-cart` Services, which were turned
   **off** in Mandate #8 §8 (pruned by ArgoCD). Those DNS names no longer resolve — the SQL
   tools and session/cache would fail on startup. Postgres is now RDS, Valkey is ElastiCache.
2. They commit `DB_PASSWORD: "otelp"` and a plaintext `DB_CONNECTION_STRING` into a tracked
   ConfigMap+Secret. Committing real secret values to tracked files is a disqualify-level TF3
   rule; the creds are also wrong (RDS uses a managed master password).
3. They deploy via raw `kubectl apply` + a manual `docker build/push` with a mutable tag
   `:v1.0.0`, bypassing GitOps and the PM-101 supply-chain gate (Trivy + Cosign, ECR immutable,
   digest-pinned).
4. Exposure/auth was left as "ClusterIP, no auth"; a customer chatbot still needs a reachable,
   gated entry point.

## Decision

Deploy the copilot through the existing TF3 platform primitives, not the handover manifests:

- **GitOps/ArgoCD** — plain manifests in `gitops/shopping-copilot/` behind a dedicated
  Application (not a techx-corp Helm chart component, since it is a standalone image and would
  otherwise trip `values.schema.json`).
- **Image through the gate** — a dedicated `build-push-copilot.yml` (Trivy HIGH/CRITICAL
  blocking gate, Cosign keyless signature) into an **IMMUTABLE** ECR repo; the deployment pins
  the image **by digest**.
- **IRSA, least-privilege** — a dedicated Bedrock role scoped to the exact model / guardrail /
  KB / bucket, mirroring `product-reviews-bedrock`. No `Resource:"*"`; no Bedrock on the shared
  workload SA.
- **Managed datastores** — DB via the RDS-managed `techx-tf3-postgres-conn` ExternalSecret;
  Valkey via a rendered `rediss://` (TLS + auth) ExternalSecret. Nothing secret in git.
- **Private exposure** — `copilot.arthur-ngo.org` behind Cloudflare Access SSO (same boundary
  as grafana/argocd), not the public storefront edge. CORS locked to that origin.

## Consequences

- The app is deployed consistently with every other TF3 service; no rule is bent.
- Two dependencies sit with AIO02 and are tracked in the deploy runbook: the Redis client must
  honour `rediss://` TLS+auth (it was built against plaintext Valkey), and the RAG Knowledge
  Base must have a live vector store (OpenSearch Serverless was turned off for cost). Both have
  graceful-degradation fallbacks, so neither blocks a first deploy — they cap functionality.
- The image digest must be filled from the first gated build before ArgoCD can pull; until then
  the pod is ImagePullBackOff, isolated from all other workloads.

## Signature

CDO02 — 2026-07-27
