from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[2]
SPOT = REPO / "gitops/karpenter/spot-nodepool.yaml"
FALLBACK = REPO / "gitops/karpenter/ondemand-fallback-nodepool.yaml"


def documents(path: Path) -> list[dict]:
    return [
        document
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
        if document
    ]


def resource(path: Path, kind: str, name: str) -> dict:
    for document in documents(path):
        if document["kind"] == kind and document["metadata"]["name"] == name:
            return document
    raise AssertionError(f"{kind}/{name} not found in {path}")


def requirements(nodepool: dict) -> dict[str, dict]:
    return {
        requirement["key"]: requirement
        for requirement in nodepool["spec"]["template"]["spec"]["requirements"]
    }


def test_arm_spot_uses_c_m_with_bounded_four_node_capacity():
    nodepool = resource(SPOT, "NodePool", "flash-sale-spot-arm64")
    requirement = requirements(nodepool)

    assert nodepool["spec"]["weight"] == 100
    assert requirement["kubernetes.io/arch"]["values"] == ["arm64"]
    assert requirement["karpenter.sh/capacity-type"]["values"] == ["spot"]
    assert requirement["karpenter.k8s.aws/instance-category"]["values"] == [
        "c",
        "m",
    ]
    assert requirement["karpenter.k8s.aws/instance-cpu"]["values"] == ["2", "4"]
    assert nodepool["spec"]["limits"] == {
        "cpu": "16",
        "memory": "64Gi",
        "nodes": 4,
    }


def test_existing_amd_spot_cap_stays_at_two_nodes():
    nodepool = resource(SPOT, "NodePool", "flash-sale-spot")
    requirement = requirements(nodepool)

    assert requirement["kubernetes.io/arch"]["values"] == ["amd64"]
    assert requirement["karpenter.sh/capacity-type"]["values"] == ["spot"]
    assert nodepool["spec"]["limits"]["nodes"] == 2
