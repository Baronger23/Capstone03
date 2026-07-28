import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TRIVYIGNORE = REPO_ROOT / "aiops-engine" / ".trivyignore"
DOCKERFILE = REPO_ROOT / "aiops-engine" / "Dockerfile"
KUBECTL_BUILDER_GO_MOD = REPO_ROOT / "aiops-engine" / "kubectl-builder" / "go.mod"
KUBECTL_BUILDER_MAIN = REPO_ROOT / "aiops-engine" / "kubectl-builder" / "main.go"
DEDICATED_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-push-aiops.yml"


def test_dedicated_gate_matches_common_zero_high_critical_policy():
    workflow = DEDICATED_WORKFLOW.read_text()

    assert not TRIVYIGNORE.exists()
    assert "--ignore-unfixed" not in workflow
    assert "--ignorefile" not in workflow
    assert '--severity "$TRIVY_SEVERITIES"' in workflow
    assert "--exit-code 1" in workflow


def test_dockerfile_builds_patched_stable_kubectl_without_changing_command_surface():
    dockerfile = DOCKERFILE.read_text()
    go_mod = KUBECTL_BUILDER_GO_MOD.read_text()
    builder_main = KUBECTL_BUILDER_MAIN.read_text()

    assert "stable.txt" not in dockerfile
    assert "dl.k8s.io/release" not in dockerfile
    assert re.search(
        r"FROM --platform=\$BUILDPLATFORM "
        r"golang:1\.26\.5@sha256:[0-9a-f]{64} AS kubectl-builder",
        dockerfile,
    )
    assert "ARG TARGETOS TARGETARCH" in dockerfile
    assert 'CGO_ENABLED=0 GOOS="$TARGETOS" GOARCH="$TARGETARCH"' in dockerfile
    assert "GOARCH=amd64" not in dockerfile
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


def test_runtime_uses_pinned_alpine_without_python_build_tooling():
    dockerfile = DOCKERFILE.read_text()

    alpine_base = (
        "python:3.10.20-alpine3.23@"
        "sha256:81c5715bb79d8edd45a82de842a29c7d6ef2aff4b7fa88e712f93a93806337df"
    )
    assert f"FROM {alpine_base} AS python-builder" in dockerfile
    assert f"FROM {alpine_base}" in dockerfile
    assert "FROM python:3.10-slim" not in dockerfile
    assert "RUN apk add --no-cache build-base" in dockerfile
    assert "RUN apk add --no-cache libgomp libstdc++" in dockerfile
    assert "RUN python -m pip uninstall -y pip setuptools wheel" in dockerfile
    assert "python -m venv /venv" in dockerfile
    assert "/venv/bin/pip uninstall -y pip setuptools wheel" in dockerfile
    assert "COPY --from=python-builder /venv /venv" in dockerfile
    assert 'ENV PATH="/venv/bin:$PATH"' in dockerfile
