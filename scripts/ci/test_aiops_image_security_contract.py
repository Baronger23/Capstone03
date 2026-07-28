import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRIVYIGNORE = REPO_ROOT / "aiops-engine" / ".trivyignore"
DOCKERFILE = REPO_ROOT / "aiops-engine" / "Dockerfile"
KUBECTL_BUILDER_GO_MOD = REPO_ROOT / "aiops-engine" / "kubectl-builder" / "go.mod"
KUBECTL_BUILDER_MAIN = REPO_ROOT / "aiops-engine" / "kubectl-builder" / "main.go"

VENDORED_SETUPTOOLS_CVES = {
    "CVE-2026-23949",
    "CVE-2026-24049",
}
KUBECTL_CVES = {
    "CVE-2026-25681",
    "CVE-2026-27136",
    "CVE-2026-33814",
    "CVE-2026-39821",
}


def _ignored_cves() -> set[str]:
    return {
        line.strip()
        for line in TRIVYIGNORE.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_trivyignore_only_suppresses_verified_vendored_setuptools_cves():
    ignored = _ignored_cves()

    assert ignored == VENDORED_SETUPTOOLS_CVES
    assert ignored.isdisjoint(KUBECTL_CVES)


def test_dockerfile_builds_patched_stable_kubectl_without_changing_command_surface():
    dockerfile = DOCKERFILE.read_text()
    go_mod = KUBECTL_BUILDER_GO_MOD.read_text()
    builder_main = KUBECTL_BUILDER_MAIN.read_text()

    assert "stable.txt" not in dockerfile
    assert "dl.k8s.io/release" not in dockerfile
    assert re.search(
        r"FROM golang:1\.26\.5@sha256:[0-9a-f]{64} AS kubectl-builder",
        dockerfile,
    )
    assert "go build -mod=readonly -trimpath" in dockerfile
    assert (
        "COPY --chmod=0755 --from=kubectl-builder "
        "/out/kubectl /usr/local/bin/kubectl"
    ) in dockerfile

    assert "k8s.io/kubectl v0.36.3" in go_mod
    assert "golang.org/x/net v0.57.0" in go_mod
    assert "golang.org/x/text v0.40.0" in go_mod
    assert "go.opentelemetry.io/otel v1.42.0" in go_mod
    assert "k8s.io/component-base/version.gitMajor=1" in dockerfile
    assert "k8s.io/component-base/version.gitMinor=36" in dockerfile
    assert "k8s.io/component-base/version.gitVersion=v1.36.3-aiops.1" in dockerfile
    assert '"k8s.io/kubectl/pkg/cmd"' in builder_main
    assert "cmd.NewDefaultKubectlCommand()" in builder_main
