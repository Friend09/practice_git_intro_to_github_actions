"""Lab 04: classify ``uses:`` references, audit action SHAs, read the real fixtures.

Run: ``uv run python labs/lab_04_whats_in_an_action.py`` (offline; values asserted).
"""

from __future__ import annotations

import json
import re

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.workflow import load_workflow

LINE = re.compile(r"Download action repository '([^']+)' \(SHA:([0-9a-f]{40})\)")


def audit(log_lines: list[str]) -> dict[str, str]:
    """Map each ``owner/repo@ref`` reference to the commit SHA the runner used."""
    resolved = {}
    for line in log_lines:
        m = LINE.search(line)
        if m:
            resolved[m.group(1)] = m.group(2)
    return resolved


def classify(ref: str) -> str:
    """Return the form of a ``uses:`` reference (local, docker, sha, tag-or-branch)."""
    if ref.startswith("./"):
        return "local"
    if ref.startswith("docker://"):
        return "docker"
    _, _, version = ref.partition("@")
    if len(version) == 40 and all(c in "0123456789abcdef" for c in version):
        return "sha"
    return "tag-or-branch"


def main() -> None:
    """Assert every claim made in Chapter 04."""
    forms = json.loads((FIXTURES_DIR / "run_ch04_forms.json").read_text())
    resolved = audit(forms["download_log_lines"])
    assert len(resolved) == 2 and len(set(resolved.values())) == 1  # tag == SHA
    assert resolved["actions/checkout@v7"].startswith("3d3c42e5aac5")

    wf = load_workflow(WORKFLOWS_DIR / "ch04-uses-forms.yml")
    uses = [s["uses"] for s in wf["jobs"]["forms"]["steps"] if "uses" in s]
    kinds = [classify(u) for u in uses]
    assert kinds == ["tag-or-branch", "sha", "local", "docker"]

    bad = json.loads((FIXTURES_DIR / "run_ch04_badref.json").read_text())
    assert bad["failed_step"] == "Set up job" and bad["steps_run"] == 1

    tags = json.loads((FIXTURES_DIR / "action_tags_2026_10.json").read_text())
    co = tags["actions/checkout"]
    assert co["tags"]["v7"] == co["tags"]["v7.0.1"] != co["tags"]["v7.0.0"]
    assert co["runtime"]["v4"] == "node20" and co["runtime"]["v7"] == "node24"
    assert "v10" in tags["astral-sh/setup-uv"]["missing_floating_tags"]
    print("kinds:", kinds, "| tag==sha:", True, "| bad ref fails at step 1")


if __name__ == "__main__":
    main()
