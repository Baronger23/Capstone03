import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("scripts/ci/read-external-image-catalog.py")
CATALOG = Path("docs/evidence/mandate-10/external-image-allowlist.yaml")


def test_scan_input_is_derived_from_the_reviewed_catalog():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--allowlist", str(CATALOG)],
        capture_output=True,
        text=True,
        check=True,
    )
    images = result.stdout.splitlines()
    assert images == sorted(images)
    # Compare against the catalogue itself rather than a frozen count. The point
    # of the check is that the scan input is derived from the reviewed list, and
    # a hardcoded number only restates today's size while breaking on every
    # legitimate catalogue change.
    catalog = yaml.safe_load(CATALOG.read_text(encoding="utf-8"))
    assert images == sorted(entry["image"] for entry in catalog["images"])
    assert images
    assert any(image.startswith("busybox@sha256:") for image in images)
    assert any(image.startswith("quay.io/kiwigrid/k8s-sidecar:") for image in images)
    assert not any("postgres" in image for image in images)
    assert not any("valkey" in image for image in images)
