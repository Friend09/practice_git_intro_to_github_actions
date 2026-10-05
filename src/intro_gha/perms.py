"""Model of GITHUB_TOKEN permission resolution (Chapter 15).

Rules (GitHub Docs, verified 2026-10, and reproduced by real probes in this repo):

- A job's ``permissions`` replace the workflow's; if neither is set the repository's
  default applies (``read`` here: contents read-only).
- If ANY permission is set, every scope not listed becomes ``none``.
- ``{}`` means all ``none``; ``read-all`` and ``write-all`` set every scope.
- ``write`` includes ``read``.
- An API call lists the permission(s) it needs in the ``X-Accepted-GitHub-Permissions``
  header: ``;`` separates alternatives, ``,`` joins permissions that are all required.
"""

from __future__ import annotations

from typing import Any

SCOPES = [
    "actions", "artifact-metadata", "attestations", "checks", "code-quality",
    "contents", "deployments", "discussions", "id-token", "issues", "packages",
    "pages", "pull-requests", "security-events", "statuses", "vulnerability-alerts",
]
LEVEL = {"none": 0, "read": 1, "write": 2}
# The "read" repository default: contents is read, every other scope none.
READ_DEFAULT = {s: ("read" if s == "contents" else "none") for s in SCOPES}


def effective(
    workflow: dict[str, Any] | str | None,
    job: dict[str, Any] | str | None,
    repo_default: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return the token's level for every scope given workflow- and job-level blocks."""
    spec = job if job is not None else workflow
    if spec is None:
        return dict(repo_default or READ_DEFAULT)
    if spec == "read-all":
        return dict.fromkeys(SCOPES, "read")
    if spec == "write-all":
        return dict.fromkeys(SCOPES, "write")
    out = dict.fromkeys(SCOPES, "none")
    for scope, level in (spec or {}).items():
        out[scope] = level
    return out


def satisfies(perms: dict[str, str], accepted: str) -> bool:
    """True if ``perms`` meets any alternative of an accepted-permissions header."""
    for alt in accepted.split(";"):
        needs = [n.split("=") for n in alt.split(",") if n]
        if needs and all(
            LEVEL[perms.get(scope.replace("_", "-"), "none")] >= LEVEL[level]
            for scope, level in needs
        ):
            return True
    return False
