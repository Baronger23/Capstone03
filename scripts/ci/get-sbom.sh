#!/usr/bin/env bash
# One-command SBOM retrieval by digest (Directive #10 requirement).
#
# Pins the Cosign major version rather than trusting whatever is on PATH.
# Images released before the v2.6.2 pin also carry OCI 1.1 referrer artifacts
# from the old pipeline. Cosign v3 resolves referrers first, finds only the old
# signature there, and reports "none of the attestations matched the predicate
# type: cyclonedx" -- even though the CycloneDX attestation is present in the
# legacy .att tag that Kyverno actually reads. Retrieval would then look broken
# on a machine whose cosign happens to be v3, so the version is enforced here.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REQUIRED_COSIGN_MAJOR=2

if ! command -v cosign >/dev/null 2>&1; then
  echo "FAIL: cosign is not on PATH; install Cosign v2.6.2 (the version the release pipeline signs with)." >&2
  exit 1
fi

cosign_version="$(cosign version 2>/dev/null | awk '/GitVersion:/ {print $2}' | tr -d 'v')"
cosign_major="${cosign_version%%.*}"

if [ "${cosign_major:-0}" != "$REQUIRED_COSIGN_MAJOR" ]; then
  cat >&2 <<EOF
FAIL: cosign v${cosign_version:-unknown} cannot read this repository's attestations.

The release pipeline signs with Cosign v2.6.2 because the Kyverno ClusterPolicy
consumes the legacy OCI layout. Cosign v3 prefers the OCI 1.1 referrers API and
will report the CycloneDX attestation as missing on any digest that predates the
v2.6.2 pin, even though the attestation exists.

Install Cosign v2.6.2 and retry:
  curl -sSL -o /usr/local/bin/cosign \\
    https://github.com/sigstore/cosign/releases/download/v2.6.2/cosign-linux-amd64
  chmod +x /usr/local/bin/cosign
EOF
  exit 1
fi

exec python3 "$SCRIPT_DIR/get-sbom.py" "$@"
