"""Find ``uses:`` references that are not pinned to a full commit SHA (Chapter 16)."""

from __future__ import annotations

import re
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def uses_refs(workflow: dict[str, Any]) -> list[str]:
    """Every ``uses:`` value in a workflow (steps and reusable-workflow job calls)."""
    refs: list[str] = []
    for job in workflow.get("jobs", {}).values():
        if "uses" in job:
            refs.append(job["uses"])
        refs += [s["uses"] for s in job.get("steps", []) if "uses" in s]
    return refs


def classify(ref: str) -> str:
    """Return ``local``, ``docker``, ``sha``, ``tag-or-branch`` or ``no-ref``."""
    if ref.startswith("./"):
        return "local"
    if ref.startswith("docker://"):
        return "docker"
    _, sep, version = ref.partition("@")
    if not sep:
        return "no-ref"
    return "sha" if SHA_RE.match(version) else "tag-or-branch"


def unpinned(workflow: dict[str, Any]) -> list[str]:
    """Remote references that are movable (not a full 40-hex commit SHA)."""
    return [r for r in uses_refs(workflow) if classify(r) in ("tag-or-branch", "no-ref")]
