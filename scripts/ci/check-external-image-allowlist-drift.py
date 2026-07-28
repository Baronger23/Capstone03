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
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="report the comparison without failing; for inspecting work in progress",
    )
    args = parser.parse_args()

    rendered = render(args.chart, args.values)
    external = {i for i in rendered if not FIRST_PARTY.match(i)}
    approved = allow_list(args.policy)

    unapproved = sorted(external - approved)
    stale = sorted(approved - external)
    tagged = sorted(i for i in external if "@sha256:" not in i)

    print(f"rendered images      : {len(rendered)}")
    print(f"first-party (signed) : {len(rendered) - len(external)}")
    print(f"external             : {len(external)}")
    print(f"allow-list entries   : {len(approved)}\n")

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
        print("Stale allow-list entries - approved but no longer rendered:")
        for image in stale:
            print(f"  {image}")
        print()

    if not (unapproved or stale or tagged):
        print("OK: every external image is digest-pinned and matches the allow-list exactly.")
        return 0

    if args.print_only:
        print("(--print-only: differences reported, exit 0)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
