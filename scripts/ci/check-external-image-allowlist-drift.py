#!/usr/bin/env python3
"""Fail when the rendered chart and the external allow-list disagree.

`allow-approved-external-image-digests` compares image strings byte for byte.
A chart bump that changes a rendered reference without the matching allow-list
edit does not fail anything at merge time - it fails later, at admission, once
the policy is in Enforce and the next pod is scheduled. That is a production
outage caused by a values change that looked harmless.

This turns that failure mode into a red PR: render the chart exactly as ArgoCD
does, split first-party from external, and require the external set to equal
the allow-list exactly - no missing entries, no stale ones.

Usage:
  check-external-image-allowlist-drift.py [--chart DIR] [--values FILE]
                                          [--policy FILE] [--print-only]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CHART = REPO / "phase3 - information" / "techx-corp-chart"
DEFAULT_VALUES = REPO / "phase3 - information" / "deploy" / "values-prod.yaml"
DEFAULT_POLICY = (
    REPO / "gitops" / "policies" / "kyverno" / "allow-approved-external-image-digests.yaml"
)
DEFAULT_GITOPS = REPO / "gitops"

# Both policies match on namespace techx-tf3, so only workloads landing there
# are judged. Anything ArgoCD installs into its own namespace is out of scope.
POLICY_NAMESPACE = "techx-tf3"

# Owned by AIO02 and running in techx-tf3, so the policy will judge them, but
# they are not ours to repin. Each one denies at admission the moment the
# external policy goes to Enforce, so they are a hard blocker for that step -
# listed here to keep them visible rather than silently passing. Remove an entry
# once AIO02 pins it; the check fails if an entry stops being needed, so the
# list cannot rot.
KNOWN_UNRESOLVED = {
    # Still bare tags, so nothing pins what they resolve to.
    "197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/tf-2-ai-engine:IF-v25",
    "197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/tf-2-ai-engine:IF-v63",
    # AIO02 pinned this to a real digest, so it already meets the external bar
    # and only needs a catalogue entry. Adding another team's image to a
    # catalogue that records TF3 review is their call, not ours, so it stays
    # here until they confirm. It cannot move to the first-party policy as
    # things stand: build-push-copilot.yml signs with Cosign but generates no
    # CycloneDX attestation, and that policy requires both.
    "197826770971.dkr.ecr.ap-southeast-1.amazonaws.com/shopping-copilot@sha256:589cb03016ae370a0532066601d1d3c8306a18112cc0e24563182aae5089a3d8",
}

# Kept in sync with the policy precondition: the optional :<tag> covers Grafana,
# whose subchart renders repo:<tag>@sha256:<digest> and cannot be repinned.
FIRST_PARTY = re.compile(
    r"^197826770971\.dkr\.ecr\.ap-southeast-1\.amazonaws\.com/techx-corp"
    r"(:[^@]+)?@sha256:[0-9a-f]{64}$"
)


def render(chart: Path, values: Path) -> set[str]:
    result = subprocess.run(
        ["helm", "template", "techx-corp", str(chart), "-f", str(values)],
        capture_output=True,
        text=True,
        check=True,
    )
    images: set[str] = set()
    for doc in yaml.safe_load_all(result.stdout):
        images |= walk(doc)
    return images


def walk(node) -> set[str]:
    """Collect every `image:` value, including init and ephemeral containers."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "image" and isinstance(value, str) and value.strip():
                found.add(value.strip())
            else:
                found |= walk(value)
    elif isinstance(node, list):
        for item in node:
            found |= walk(item)
    return found


def gitops_images(root: Path) -> set[str]:
    """Images from plain manifests, which the chart render never sees.

    cloudflared and the AIO02 workloads are applied straight from gitops/, so a
    chart-only check would call them stale forever and stay red for the wrong
    reason.
    """
    images: set[str] = set()
    for path in sorted(root.rglob("*.yaml")):
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except yaml.YAMLError:
            continue
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if (doc.get("metadata") or {}).get("namespace") != POLICY_NAMESPACE:
                continue
            images |= walk(doc)
    return images


def allow_list(policy: Path) -> set[str]:
    doc = yaml.safe_load(policy.read_text(encoding="utf-8"))
    entries: set[str] = set()
    for rule in doc["spec"]["rules"]:
        for each in rule["validate"]["foreach"]:
            for condition in each["deny"]["conditions"]["any"]:
                entries |= set(condition["value"])
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--values", type=Path, default=DEFAULT_VALUES)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--gitops", type=Path, default=DEFAULT_GITOPS)
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="report the comparison without failing; for inspecting work in progress",
    )
    args = parser.parse_args()

    rendered = render(args.chart, args.values) | gitops_images(args.gitops)
    external = {i for i in rendered if not FIRST_PARTY.match(i)}
    approved = allow_list(args.policy)

    deferred = external & KNOWN_UNRESOLVED
    judged = external - KNOWN_UNRESOLVED

    unapproved = sorted(judged - approved)
    stale = sorted(approved - judged)
    tagged = sorted(i for i in judged if "@sha256:" not in i)
    # An exception that no longer matches anything is a lie about the risk.
    obsolete = sorted(KNOWN_UNRESOLVED - external)

    print(f"images in scope      : {len(rendered)}")
    print(f"first-party (signed) : {len(rendered) - len(external)}")
    print(f"external             : {len(external)}")
    print(f"allow-list entries   : {len(approved)}\n")

    if deferred:
        print("BLOCKS ENFORCE - owned by AIO02, will deny at admission:")
        for image in sorted(deferred):
            print(f"  {image}")
        print()

    if unapproved:
        print("DENIED under Enforce - rendered but not in the allow-list:")
        for image in unapproved:
            print(f"  {image}")
        print()
    if tagged:
        print("Pinned by tag - a tag can be repointed upstream, so it is not a pin:")
        for image in tagged:
            print(f"  {image}")
        print()
    if stale:
        print("Stale allow-list entries - approved but nothing renders them:")
        for image in stale:
            print(f"  {image}")
        print()
    if obsolete:
        print("Obsolete exceptions - listed in KNOWN_UNRESOLVED but no longer deployed;")
        print("delete them so the list keeps telling the truth:")
        for image in obsolete:
            print(f"  {image}")
        print()

    if not (unapproved or stale or tagged or obsolete):
        print("OK: every external image is digest-pinned and matches the allow-list exactly.")
        if deferred:
            print(f"NOTE: {len(deferred)} AIO02 image(s) still block Enforce - see above.")
        return 0

    if args.print_only:
        print("(--print-only: differences reported, exit 0)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
