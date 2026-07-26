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
