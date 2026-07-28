# AIOps Common Supply-Chain Migration Design

## Goal

Move `aiops-engine` from its dedicated image workflow into
`.github/workflows/build-push-ecr.yml` without losing remediation or training
functionality. Every promoted AIOps image must be a multi-platform
`techx-corp` image with pre-push and post-push Trivy evidence, a keyless Cosign
signature, and the CycloneDX attestations required by
`verify-first-party-signatures`.

## Verified constraints

- AIOps source and `.dockerignore` live at repository root under
  `aiops-engine/`; the compose file lives two levels below it under
  `phase3 - information/techx-corp-platform/`.
- The common workflow builds `linux/amd64,linux/arm64`, but the current
  kubectl builder hardcodes `GOARCH=amd64`.
- The common Trivy gate blocks every HIGH/CRITICAL finding. The patched
  candidate still reports 37 Debian findings without an upstream fix plus two
  fixable findings in setuptools-vendored metadata.
- The two vendored findings are `CVE-2026-23949` and `CVE-2026-24049`.
  No kubectl CVE may be ignored.
- The common image-bump job only edits
  `phase3 - information/deploy/values-prod.yaml`; AIOps uses standalone
  manifests under `gitops/aiops-engine/`.
- The final `techx-corp` digest does not exist until the workflow runs from
  `main`. Removing the old external-image entries before promotion would make
  rescheduled old AIOps pods fail Kyverno admission.
- The new image owns `/app` as UID 10001. The training CronJob currently runs
  as UID/GID 1000 and writes model files under `/app/models`.

## Architecture

### Phase A: build-path integration

Draft PR #544 will:

1. Add compose bake target `aiops-engine` with build context
   `../../aiops-engine` and Dockerfile `Dockerfile`.
2. Add `aiops-engine/**` to the common workflow trigger and map root AIOps
   changes to the scoped `aiops-engine` service in both duplicated scope
   resolvers.
3. Register `aiops-engine` in every fail-closed service allowlist, including
   image-bump validation.
4. Make the kubectl builder use BuildKit `TARGETOS` and `TARGETARCH`, preserving
   the Kubernetes 1.36 command tree on both supported platforms.
5. Move the two setuptools-vendored exceptions out of
   `aiops-engine/.trivyignore` into a pipeline-owned, service-scoped ignorefile.
   Only AIOps scans receive `--ignore-unfixed`; full JSON reports still retain
   every suppressed and unfixed finding.
6. Delete `.github/workflows/build-push-aiops.yml` and
   `aiops-engine/.trivyignore`.
7. Extend image-bump automation so an approved `aiops-engine` artifact produces
   an atomic promotion diff for the standalone Deployment, CronJob, Kyverno
   external catalogue, and mandate evidence catalogue.

Phase A deliberately retains the running `tf-2-ai-engine` manifest references
and their allowlist entries. Merging Phase A therefore causes no Argo rollout
and no admission gap.

### Phase B: generated promotion

After Phase A merges, the common workflow builds and verifies the AIOps image.
Only after all pre-push scan, push, post-push scan, signature, SBOM generation,
attestation, and verification gates pass may the image-bump job open a
promotion PR.

That generated PR will atomically:

- set both `gitops/aiops-engine/deployment.yaml` and `cronjob.yaml` to the same
  immutable `techx-corp:<tag>@sha256:<digest>` image;
- align the training pod UID, GID, and fsGroup to 10001 so it can write
  `/app/models`;
- remove the two obsolete `tf-2-ai-engine` references from all three container
  branches in `allow-approved-external-image-digests.yaml`;
- remove the two matching entries from
  `docs/evidence/mandate-10/external-image-allowlist.yaml`.

Argo CD can reconcile this promotion only after the first-party signature and
SBOM attestations already exist.

## Trivy policy

The common pipeline will keep two distinct outputs:

- a complete JSON report with all findings for audit evidence;
- a blocking AIOps gate that uses `--ignore-unfixed` and a service-scoped
  ignorefile containing only the two verified setuptools-vendored CVEs.

All other services retain the existing zero-HIGH/CRITICAL policy. Both local
pre-push and immutable post-push scans must use the same service policy.

## Context and `.dockerignore` verification

Before delivery, verification must prove:

1. `docker buildx bake --print aiops-engine` resolves the context to the
   repository-root `aiops-engine` directory and resolves `Dockerfile` relative
   to that context.
2. Temporary sentinel files under `aiops-engine/models/` and
   `aiops-engine/scratch/` do not appear in the built image.
3. The shipped image contains no `.joblib` file from the build context.
4. Both amd64 and arm64 kubectl binaries match their image platform and expose
   the required `scale`, `rollout`, and `exec` commands.

## Testing

- Contract tests cover workflow trigger/scope registration, service allowlists,
  service-scoped Trivy arguments, bake context, multi-platform kubectl build,
  and exact promotion file scope.
- Image-bump tests prove an AIOps-only approved manifest changes exactly the two
  AIOps manifests and removes exactly the old catalogue entries.
- Existing Helm image-bump behavior remains unchanged for all chart services.
- Local bake, Trivy, `govulncheck`, application import, deterministic AIOps
  tests, YAML parsing, policy tests, and workflow contract tests run before the
  implementation is pushed.

## Non-goals

- Do not replace kubectl shell-outs with the Kubernetes Python client.
- Do not modify AIOps remediation logic, RBAC, flagd/OpenFeature, secrets, or
  live production objects.
- Do not merge the promotion PR or manually sync Argo CD.
