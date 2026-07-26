# PM-176 post-PR #475 Trivy block and trust decision

Captured: 2026-07-26 UTC from Actions run `30214865296`, job
`89827218482`.

## Gate result

The build completed, but the blocking pre-push Trivy gate rejected the
`linux/amd64` candidate before any ECR push. Production therefore remained on
the previous digest.

The operating-system layer and custom Grafana binary had zero HIGH/CRITICAL
findings. All four HIGH findings belonged to the signed OpenSearch plugin
backend:

| Finding | Detected | Fixed |
| --- | --- | --- |
| `GHSA-hrxh-6v49-42gf` | `google.golang.org/grpc v1.79.3` | `1.82.1` |
| `CVE-2026-27145` | Go stdlib `1.26.3` | `1.26.4` |
| `CVE-2026-39822` | Go stdlib `1.26.3` | `1.26.5` |
| `CVE-2026-42504` | Go stdlib `1.26.3` | `1.26.4` |

The exact target was
`/opt/grafana/plugins/grafana-opensearch-datasource/gpx_opensearch-datasource_linux_amd64`.

## Why an ignore rule is rejected

PM-101 requires zero HIGH/CRITICAL findings for a first-party candidate. The
findings have published fixed versions, and no newer signed OpenSearch plugin
release exists at capture time. Adding a blanket or temporary Trivy ignore
would make the build green without removing the vulnerable code and would
weaken the established release gate.

## Corrective design

Build the backend from the exact OpenSearch datasource 2.34.0 release commit
`188f6f20d488f771808eff476e8647dccb901dad`, with:

- pinned Go builder `1.26.5`;
- `google.golang.org/grpc v1.82.1`;
- `CGO_ENABLED=0`, target OS and architecture explicitly set.

The official 2.34.0 archive continues to provide the frontend assets. Because
replacing the backend invalidates the upstream signature, the upstream
`MANIFEST.txt` is removed rather than left in a misleading modified state.
Grafana allows only the exact
`grafana-opensearch-datasource` unsigned plugin ID.

Compensating integrity controls are:

- plugin source commit and builder image digest pinned in the Dockerfile;
- plugin directory owned by root and made read-only;
- no runtime plugin installer or update path;
- first-party image digest pinning, Trivy zero-HIGH/CRITICAL gate, SBOM, and
  GitHub OIDC Cosign signing/verification;
- runtime smoke test must prove that the plugin and `webstore-logs` datasource
  load successfully.

This is narrower than disabling signature verification globally and keeps the
Trivy gate fail-closed.

## PR #476 verification contract

The candidate now carries the following immutable inputs:

- OpenSearch source commit:
  `188f6f20d488f771808eff476e8647dccb901dad`.
- Dependency patch SHA-256:
  `940f564bba915faa6762cba49eed07599bd70c9677fc8702143f9a98dce60091`.
- Grafana Catalog `2.34.0` archive SHA-256:
  - amd64:
    `fcd1bedfccde21ca224139bf409170c194a9a34cdda2f8756b8427b6775ca611`
  - arm64:
    `8c644c95b3ac39dedf8254cc99d3921b136fe06895f5a8aeb17cfa0a709e7da6`

The Dockerfile verifies the patch, `go mod verify`, both architecture-specific
archives, and the CLI-installed tree before replacing only the backend. It
then removes the stale upstream `MANIFEST.txt` and writes
`TF3-PROVENANCE` with the source, archive, Go, grpc, and trust-model values.

`.github/workflows/verify-grafana-image.yml` is a read-only pull-request gate.
It builds and scans `linux/amd64` and `linux/arm64` separately with Trivy
`HIGH,CRITICAL --exit-code 1`, then performs an amd64 startup smoke. The smoke
sets `GF_PLUGINS_PREINSTALL_DISABLED=true` (an empty `GF_PLUGINS_PREINSTALL`
does not disable Grafana 13's default catalog), checks health and provenance,
requires plugin registration, and rejects runtime install/download/signature
errors. It does not use AWS credentials, ECR, OIDC, or write permissions.

Production evidence is still pending the GitHub check and operator-only
ArgoCD/runtime smoke after merge. The previous production digest remains
unchanged until those gates pass.
