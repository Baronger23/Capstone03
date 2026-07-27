#!/usr/bin/env bash
# Backfill Cosign signature + CycloneDX SBOM evidence onto first-party index
# digests that are already in ECR.
#
# This exists because images released before the Cosign v2.6.2 pin (PR #490)
# were signed with the OCI 1.1 referrers layout, which Kyverno's verifyImages
# cannot read. Those digests are running in production, so they must gain
# legacy-layout evidence before `verify-first-party-signatures` can move to
# Enforce -- otherwise admission would reject every live first-party workload.
#
# It never rebuilds, never pushes a new tag, and never mutates the image bytes:
# the index digest before and after a backfill is identical. Anything else
# would be a release, not a backfill.
#
# ECR tag immutability allows exactly one `.sig` and one `.att` write per
# subject digest, and Cosign's legacy layout stores every predicate type for a
# digest under that single `.att` tag. A digest that already carries evidence
# therefore cannot be re-attested -- see the pre-flight check below.
#
# MUST run from GitHub Actions on main: the keyless identity baked into the
# ClusterPolicy is build-push-ecr.yml@refs/heads/main. Signing from a
# workstation produces a different identity and Kyverno will still reject it.
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
usage: backfill-cosign-evidence.sh --pairs "<service>=<digest> [<service>=<digest> ...]"
                                   --registry <registry> --repository <repo>
                                   --platforms <csv> --source-sha <sha>
                                   --identity <workflow identity> --evidence-root <dir>
USAGE
  exit 2
}

PAIRS="" REGISTRY="" REPOSITORY="" PLATFORMS="" SOURCE_SHA="" IDENTITY="" EVIDENCE_ROOT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --pairs) PAIRS="$2"; shift 2 ;;
    --registry) REGISTRY="$2"; shift 2 ;;
    --repository) REPOSITORY="$2"; shift 2 ;;
    --platforms) PLATFORMS="$2"; shift 2 ;;
    --source-sha) SOURCE_SHA="$2"; shift 2 ;;
    --identity) IDENTITY="$2"; shift 2 ;;
    --evidence-root) EVIDENCE_ROOT="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; usage ;;
  esac
done

for required in PAIRS REGISTRY REPOSITORY PLATFORMS SOURCE_SHA IDENTITY EVIDENCE_ROOT; do
  if [ -z "${!required}" ]; then
    echo "FAIL: --${required,,} is required" >&2
    usage
  fi
done

ISSUER="https://token.actions.githubusercontent.com"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RAW_ROOT="$EVIDENCE_ROOT/sbom/raw"
MANIFEST_ROOT="$EVIDENCE_ROOT/sbom/manifests"
PLATFORM_ROOT="$EVIDENCE_ROOT/sbom/platforms"
PREDICATE_ROOT="$EVIDENCE_ROOT/sbom/predicates"
VERIFY_ROOT="$EVIDENCE_ROOT/sbom/verify"
SUMMARY="$EVIDENCE_ROOT/backfill-evidence.jsonl"
mkdir -p "$RAW_ROOT" "$MANIFEST_ROOT" "$PLATFORM_ROOT" "$PREDICATE_ROOT" "$VERIFY_ROOT"
: > "$SUMMARY"

read -r -a PAIR_ARRAY <<< "$PAIRS"
if [ "${#PAIR_ARRAY[@]}" -eq 0 ]; then
  echo "FAIL: no <service>=<digest> pairs supplied" >&2
  exit 1
fi

# Pre-flight: reject malformed input and digests that already carry evidence,
# before any registry write happens. A partial backfill would leave a digest
# permanently un-completable, because the .att tag can only be written once.
declare -a SERVICES=() DIGESTS=()
for pair in "${PAIR_ARRAY[@]}"; do
  service="${pair%%=*}"
  digest="${pair#*=}"
  if [ -z "$service" ] || [ -z "$digest" ] || [ "$service" = "$pair" ]; then
    echo "FAIL: malformed pair '$pair', expected <service>=<digest>" >&2
    exit 1
  fi
  if ! [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "FAIL: '$service' digest is not a sha256 digest: $digest" >&2
    exit 1
  fi
  SERVICES+=("$service")
  DIGESTS+=("$digest")
done

echo "== Pre-flight: checking for existing Cosign evidence =="
preflight_failed=false
for i in "${!SERVICES[@]}"; do
  digest="${DIGESTS[$i]}"
  tag_prefix="${digest/:/-}"
  existing="$(aws ecr describe-images \
    --repository-name "$REPOSITORY" \
    --image-ids "imageTag=${tag_prefix}.att" \
    --query 'imageDetails[0].imageDigest' \
    --output text 2>/dev/null || true)"
  if [ -n "$existing" ] && [ "$existing" != "None" ]; then
    echo "  FAIL ${SERVICES[$i]} $digest already has a ${tag_prefix}.att tag" >&2
    echo "       ECR immutability forbids a second write; this digest must be rebuilt, not backfilled." >&2
    preflight_failed=true
  else
    echo "  ok   ${SERVICES[$i]} $digest"
  fi
done
if [ "$preflight_failed" = true ]; then
  echo "FAIL: pre-flight rejected at least one digest; nothing was written." >&2
  exit 1
fi

for i in "${!SERVICES[@]}"; do
  service="${SERVICES[$i]}"
  index_digest="${DIGESTS[$i]}"
  index_image="${REGISTRY}/${REPOSITORY}@${index_digest}"
  manifest_raw="$MANIFEST_ROOT/${service}.json"
  platform_map="$PLATFORM_ROOT/${service}.json"

  echo "== $service $index_digest =="

  echo "Signing $index_image"
  cosign sign --yes "$index_image"
  cosign verify \
    --certificate-oidc-issuer "$ISSUER" \
    --certificate-identity "$IDENTITY" \
    "$index_image" > "$VERIFY_ROOT/${service}-signature.json"

  echo "Resolving OCI platform children for $index_image"
  docker buildx imagetools inspect --raw "$index_image" > "$manifest_raw"
  python3 "$SCRIPT_DIR/resolve-oci-platforms.py" \
    --input "$manifest_raw" \
    --image "$index_image" \
    --expected-platforms "$PLATFORMS" \
    --output "$platform_map"

  # Mirrors the release path: every platform gets its own child attestation,
  # and the index carries exactly one CycloneDX reference (first platform).
  index_reference_emitted=false
  while IFS= read -r platform_entry; do
    platform="$(jq -r '.platform' <<< "$platform_entry")"
    child_digest="$(jq -r '.digest' <<< "$platform_entry")"
    child_image="$(jq -r '.image' <<< "$platform_entry")"
    safe_platform="${platform//\//-}"
    raw="$RAW_ROOT/${service}-${safe_platform}.json"
    predicate="$PREDICATE_ROOT/${service}-${safe_platform}.json"

    echo "Generating CycloneDX SBOM for $child_image ($platform)"
    trivy image \
      --platform "$platform" \
      --format cyclonedx \
      --output "$raw" \
      --no-progress \
      "$child_image"

    python3 "$SCRIPT_DIR/prepare-cyclonedx-sbom.py" \
      --input "$raw" \
      --output "$predicate" \
      --image "$child_image" \
      --platform "$platform" \
      --index-digest "$index_digest" \
      --subject-digest "$child_digest" \
      --source-sha "$SOURCE_SHA"

    echo "Attesting CycloneDX SBOM for child $child_image ($platform)"
    cosign attest --yes --type cyclonedx --predicate "$predicate" "$child_image"
    cosign verify-attestation \
      --type cyclonedx \
      --certificate-oidc-issuer "$ISSUER" \
      --certificate-identity "$IDENTITY" \
      "$child_image" > "$VERIFY_ROOT/${service}-${safe_platform}-child.jsonl"

    if [ "$index_reference_emitted" = false ]; then
      echo "Attesting CycloneDX SBOM reference on index $index_image ($platform)"
      cosign attest --yes --type cyclonedx --predicate "$predicate" "$index_image"
      cosign verify-attestation \
        --type cyclonedx \
        --certificate-oidc-issuer "$ISSUER" \
        --certificate-identity "$IDENTITY" \
        "$index_image" > "$VERIFY_ROOT/${service}-index.jsonl"
      index_reference_emitted=true
    fi

    jq -nc \
      --arg service "$service" \
      --arg index_digest "$index_digest" \
      --arg child_digest "$child_digest" \
      --arg platform "$platform" \
      --arg source_sha "$SOURCE_SHA" \
      --arg identity "$IDENTITY" \
      --arg issuer "$ISSUER" \
      '{
        service: $service,
        indexDigest: $index_digest,
        childDigest: $child_digest,
        platform: $platform,
        sourceSha: $source_sha,
        signatureIdentity: $identity,
        signatureIssuer: $issuer,
        sbomPredicateType: "https://cyclonedx.org/bom",
        method: "backfill",
        result: "PASS"
      }' >> "$SUMMARY"
  done < <(jq -c '.platforms[]' "$platform_map")

  if [ "$index_reference_emitted" != true ]; then
    echo "FAIL: $service resolved no platforms, so no index attestation was written" >&2
    exit 1
  fi
done

echo "== Backfill complete: $(wc -l < "$SUMMARY") platform records =="
