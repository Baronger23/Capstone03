import re
from pathlib import Path


WORKFLOW = Path(".github/workflows/build-push-ecr.yml").read_text()


def test_workflow_generates_and_verifies_platform_sbom_attestations():
    assert "Generate, attest, and verify CycloneDX SBOMs" in WORKFLOW
    assert "--format cyclonedx" in WORKFLOW
    assert "--platform \"$platform\"" in WORKFLOW
    assert "prepare-cyclonedx-sbom.py" in WORKFLOW
    assert "cosign attest" in WORKFLOW
    assert "cosign verify-attestation" in WORKFLOW
    assert "--type cyclonedx" in WORKFLOW
    assert "resolve-oci-platforms.py" in WORKFLOW
    assert "docker buildx imagetools inspect --raw" in WORKFLOW
    assert "--subject-digest \"$child_digest\"" in WORKFLOW
    assert "--index-digest \"$index_digest\"" in WORKFLOW
    assert 'done < <(jq -c \'.platforms[]\' "$platform_map")' in WORKFLOW
    assert "--source-sha \"$SOURCE_SHA\"" in WORKFLOW


def test_workflow_uses_exact_github_oidc_identity_for_sbom():
    assert 'EXPECTED_IDENTITY="https://github.com/${GITHUB_WORKFLOW_REF}"' in WORKFLOW
    assert "--certificate-oidc-issuer https://token.actions.githubusercontent.com" in WORKFLOW
    assert 'predicateType: "https://cyclonedx.org/bom"' in WORKFLOW
    assert "sbom-index.json" in WORKFLOW


def test_workflow_uses_clusterpolicy_compatible_cosign_storage():
    installer = WORKFLOW.index("sigstore/cosign-installer@")
    signing = WORKFLOW.index("Sign and verify approved image digests with keyless Cosign")
    install_block = WORKFLOW[installer:signing]
    assert "cosign-release: v2.6.2" in install_block


def test_workflow_signs_before_generating_or_attesting_sbom():
    signing = WORKFLOW.index("Sign and verify approved image digests with keyless Cosign")
    generation = WORKFLOW.index("Generate, attest, and verify CycloneDX SBOMs")
    assert signing < generation
    assert WORKFLOW.index("cosign sign --yes", signing) < WORKFLOW.index(
        "cosign attest", generation
    )


def test_sbom_generation_precedes_release_evidence_upload():
    generation = WORKFLOW.index("Generate, attest, and verify CycloneDX SBOMs")
    upload = WORKFLOW.index("Upload signed release evidence")
    assert generation < upload


def test_workflow_does_not_allow_pending_sbom_or_skip_attestation():
    assert "allow-pending-sbom" not in WORKFLOW
    assert "if-no-files-found: warn" in WORKFLOW
    assert "if-no-files-found: error" in WORKFLOW


def test_workflow_emits_one_index_sbom_reference_for_immutable_ecr():
    assert "index_reference_emitted=false" in WORKFLOW
    assert 'if [ "$index_reference_emitted" = false ]; then' in WORKFLOW
    assert "index_reference_emitted=true" in WORKFLOW
    assert WORKFLOW.count(
        'echo "Attesting CycloneDX SBOM reference on index $index_image ($platform)"'
    ) == 1


def test_workflow_writes_the_index_attestation_tag_exactly_once():
    """ECR immutable tags accept one `.att` write per subject digest, and the
    Cosign legacy layout stores every predicate type for a digest under that one
    tag. A second `cosign attest` on the index -- whatever its --type -- fails
    with TAG_INVALID, so the index may only ever be attested once (cyclonedx).
    """
    sbom_step = WORKFLOW[WORKFLOW.index("Generate, attest, and verify CycloneDX SBOMs"):]
    attest_targets = re.findall(r'cosign attest \\\n(?:\s+--[^\n]*\\\n)*\s+"\$(\w+)"', sbom_step)
    assert attest_targets.count("index_image") == 1
    # The mapping is still built as a release-evidence artifact, so the variable
    # survives; only pushing it to the registry as a second attestation is banned.
    assert '--type "$INDEX_PREDICATE_TYPE"' not in sbom_step
