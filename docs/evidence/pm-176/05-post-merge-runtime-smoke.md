# PM-176 post-merge runtime smoke

Captured: 2026-07-27 UTC after PR #476 and image-bump PR #478 merged.

## Passed checks

- ArgoCD `techx-corp`: `Synced/Healthy`, revision
  `4e4f2e4784d6e32098cec57a7639a7dadeed6719`.
- Grafana deployment image:
  `b44ca10-30240572310-grafana@sha256:198bff3b9b5f15962cf0942f38a0a90226f60277e7ef5212294987d160f55958`.
- Grafana Pod `grafana-668bb9ccc5-t4kbl`: all four containers Ready,
  zero restarts.
- `GF_PATHS_PLUGINS=/opt/grafana/plugins`.
- Grafana config disables preinstall, auto-update, and plugin administration;
  only `grafana-opensearch-datasource` is allowlisted.
- Startup log contains `Plugin registered` for
  `grafana-opensearch-datasource` and no runtime install/download/signature
  failure.
- Grafana API health returns `database=ok`; plugin metadata reports version
  `2.34.0`; datasource `webstore-logs` has the expected plugin type.

## Failed functional check

Datasource health returned:

```json
{"message":"Index not found: otel-logs-*","status":"ERROR"}
```

OpenSearch itself is healthy enough to serve the existing daily indices:
`otel-logs-2026-07-24` through `otel-logs-2026-07-27`. The wildcard is therefore
being treated as a literal index by the plugin health endpoint, while the
dashboard PPL queries can still use `source=otel-logs-*`.

The corrective GitOps change uses Grafana's supported daily time-pattern
syntax, `[otel-logs-]YYYY-MM-DD`, so Save & Test resolves the current daily
index without changing the dashboard query sources. No live datasource or
OpenSearch mutation was made during this capture.

The plugin provenance file could not be read with the readonly identity
because `pods/exec` is not granted; the immutable image digest and build
evidence remain verified.
