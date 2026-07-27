import hashlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
CHART = REPO / "phase3 - information" / "techx-corp-chart"
VALUES = [
    CHART / "values.yaml",
    REPO / "phase3 - information" / "deploy" / "values-flagd-sync.yaml",
    REPO / "phase3 - information" / "deploy" / "values-prod.yaml",
    REPO / "phase3 - information" / "deploy" / "values-aio-llm.yaml",
]
SMOKE = REPO / "scripts" / "pm-176-grafana-smoke.sh"
DOCKERFILE = (
    REPO
    / "phase3 - information"
    / "techx-corp-platform"
    / "src"
    / "grafana"
    / "Dockerfile"
)
PLUGIN_PATCH = (
    REPO
    / "phase3 - information"
    / "techx-corp-platform"
    / "src"
    / "grafana"
    / "patches"
    / "opensearch-grpc-1.82.1.patch"
)
OPENSEARCH_DATASOURCE = (
    REPO
    / "phase3 - information"
    / "techx-corp-chart"
    / "grafana"
    / "provisioning"
    / "datasources"
    / "opensearch.yaml"
)
PREMERGE_WORKFLOW = REPO / ".github" / "workflows" / "verify-grafana-image.yml"
PLUGIN_PATH = "/opt/grafana/plugins"
PLUGIN_SETTINGS = {
    "allow_loading_unsigned_plugins": "grafana-opensearch-datasource",
    "preinstall_disabled": True,
    "preinstall_auto_update": False,
    "plugin_admin_enabled": False,
    "plugin_admin_external_manage_enabled": False,
}
IMAGE_RE = re.compile(
    r"^197826770971\.dkr\.ecr\.ap-southeast-1\.amazonaws\.com/"
    r"techx-corp:[A-Za-z0-9_.-]+-grafana@sha256:[0-9a-f]{64}$"
)


def render_production() -> list[dict]:
    with tempfile.TemporaryDirectory() as tmpdir:
        chart_copy = Path(tmpdir) / CHART.name
        shutil.copytree(CHART, chart_copy)
        subprocess.run(
            ["helm", "dependency", "build", str(chart_copy)],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
        values = [chart_copy / "values.yaml", *VALUES[1:]]
        result = subprocess.run(
            [
                "helm",
                "template",
                "techx-corp",
                str(chart_copy),
                "--namespace",
                "techx-tf3",
                *sum((["-f", str(path)] for path in values), []),
            ],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
        return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def named_document(documents: list[dict], kind: str, name: str) -> dict:
    return next(
        doc
        for doc in documents
        if doc.get("kind") == kind
        and (doc.get("metadata") or {}).get("name") == name
    )


@pytest.mark.skipif(shutil.which("helm") is None, reason="helm is required")
def test_pm176_render_uses_baked_plugin_without_runtime_installer():
    documents = render_production()
    deployment = named_document(documents, "Deployment", "grafana")
    pod_spec = deployment["spec"]["template"]["spec"]
    containers = {
        container["name"]: container for container in pod_spec["containers"]
    }
    grafana = containers["grafana"]

    assert IMAGE_RE.fullmatch(grafana["image"])
    plugin_path_env = [
        item for item in grafana["env"] if item["name"] == "GF_PATHS_PLUGINS"
    ]
    assert plugin_path_env == [
        {"name": "GF_PATHS_PLUGINS", "value": PLUGIN_PATH}
    ]
    assert not any(
        item["name"].startswith("GF_PLUGINS_PREINSTALL")
        for item in grafana["env"]
    )

    all_containers = [
        *pod_spec.get("initContainers", []),
        *pod_spec["containers"],
    ]
    startup_text = " ".join(
        str(value)
        for container in all_containers
        for key in ("command", "args")
        for value in container.get(key, [])
    )
    assert "grafana-opensearch-datasource" not in startup_text
    assert "plugins install" not in startup_text

    assert {
        "grafana-sc-alerts",
        "grafana-sc-dashboard",
        "grafana-sc-datasources",
    }.issubset(containers)
    security_context = grafana["securityContext"]
    assert security_context["runAsNonRoot"] is True
    assert security_context["allowPrivilegeEscalation"] is False
    assert security_context["capabilities"]["drop"] == ["ALL"]
    assert security_context["seccompProfile"]["type"] == "RuntimeDefault"

    configmap = named_document(documents, "ConfigMap", "grafana")
    grafana_ini = configmap["data"]["grafana.ini"]
    assert "[paths]" in grafana_ini
    assert f"plugins = {PLUGIN_PATH}" in grafana_ini
    assert "[analytics]" in grafana_ini
    assert "check_for_updates = false" in grafana_ini
    assert "reporting_enabled = false" in grafana_ini
    assert "[plugins]" in grafana_ini
    for key, value in PLUGIN_SETTINGS.items():
        assert f"{key} = {str(value).lower()}" in grafana_ini


def test_pm176_base_values_do_not_declare_runtime_plugins():
    values = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    grafana = values["grafana"]

    assert "plugins" not in grafana
    assert grafana["grafana.ini"]["paths"]["plugins"] == PLUGIN_PATH
    assert grafana["grafana.ini"]["analytics"] == {
        "check_for_updates": False,
        "reporting_enabled": False,
    }
    assert grafana["grafana.ini"]["plugins"] == PLUGIN_SETTINGS


def test_pm176_opensearch_datasource_uses_daily_time_pattern():
    datasource = yaml.safe_load(OPENSEARCH_DATASOURCE.read_text(encoding="utf-8"))
    item = datasource["datasources"][0]

    assert item["uid"] == "webstore-logs"
    assert item["type"] == "grafana-opensearch-datasource"
    assert item["jsonData"]["database"] == "[otel-logs-]YYYY-MM-DD"
    assert item["jsonData"]["pplEnabled"] is True


def test_pm176_smoke_script_is_read_only_and_syntax_valid():
    script = SMOKE.read_text(encoding="utf-8")
    assert shutil.which("bash") is not None
    subprocess.run(["bash", "-n", str(SMOKE)], cwd=REPO, check=True)
    for forbidden in ("kubectl apply", "kubectl patch", "kubectl delete", "kubectl rollout"):
        assert forbidden not in script
    for required in (
        "GF_PATHS_PLUGINS",
        "allow_loading_unsigned_plugins = grafana-opensearch-datasource",
        "preinstall_disabled = true",
        "failed to install plugin",
        "modified signature",
        "plugin validation failed",
        "grafana-opensearch-datasource/plugin.json",
        "/api/datasources/uid/webstore-logs",
        "EXPECT_EGRESS_BLOCK",
        "kubectl port-forward",
    ):
        assert required in script


def test_pm176_dockerfile_locks_derived_plugin_provenance():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    patch_hash = hashlib.sha256(PLUGIN_PATCH.read_bytes()).hexdigest()

    assert "sha256sum /tmp/opensearch-grpc-1.82.1.patch" in dockerfile
    assert patch_hash in dockerfile
    assert "git apply --check /tmp/opensearch-grpc-1.82.1.patch" in dockerfile
    assert "go mod download" in dockerfile
    assert "go mod verify" in dockerfile
    assert "go get google.golang.org/grpc@v1.82.1" not in dockerfile
    assert "diff -qr" in dockerfile
    assert "TF3-PROVENANCE" in dockerfile
    assert "trust_model=tf3-derived-unsigned" in dockerfile
    assert "rm \"${GF_PATHS_PLUGINS}/grafana-opensearch-datasource/MANIFEST.txt\"" in dockerfile
    assert (
        "ADD --checksum=sha256:fcd1bedfccde21ca224139bf409170c194a9a34cdda2f8756b8427b6775ca611"
        in dockerfile
    )
    assert (
        "ADD --checksum=sha256:8c644c95b3ac39dedf8254cc99d3921b136fe06895f5a8aeb17cfa0a709e7da6"
        in dockerfile
    )


def test_pm176_premerge_image_gate_is_read_only_and_dual_arch():
    workflow = PREMERGE_WORKFLOW.read_text(encoding="utf-8")

    assert '"on":' in workflow
    assert "pull_request:" in workflow
    assert "phase3 - information/techx-corp-platform/src/grafana/**" in workflow
    assert "linux/amd64" in workflow
    assert "linux/arm64" in workflow
    assert "--severity HIGH,CRITICAL" in workflow
    assert "--exit-code 1" in workflow
    assert "--retry-all-errors" in workflow
    assert 'msg="Plugin registered" pluginId=grafana-opensearch-datasource' in workflow
    assert 'docker logs "${container}" > "${report}" 2>&1' in workflow
    assert 'docker logs "${container}" 2>&1 |' not in workflow
    assert "actions/upload-artifact@" in workflow
    assert "persist-credentials: false" in workflow
    for forbidden in (
        "configure-aws-credentials",
        "amazon-ecr-login",
        "AWS_ROLE_ARN",
        "id-token: write",
        "contents: write",
        "docker push",
    ):
        assert forbidden not in workflow
