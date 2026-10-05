"""Lab 15: predict the token permission matrix and read the real probe results.

Run: ``uv run python labs/lab_15_token_and_permissions.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.perms import SCOPES, effective, satisfies
from intro_gha.workflow import load_workflow

JOBS = {
    "none": {},
    "contents_read": {"contents": "read"},
    "contents_write": {"contents": "write"},
    "issues_write": {"issues": "write"},
    "both_write": {"contents": "write", "issues": "write"},
    "write_all": "write-all",
}


def main() -> None:
    """Assert every claim made in Chapter 15."""
    s = json.loads((FIXTURES_DIR / "token_ch15_summary.json").read_text())
    assert len(SCOPES) == s["docs"]["scopes"] == 16

    cells = 0
    for job, block in JOBS.items():
        perms = effective({"contents": "read"}, block)  # a job block replaces the workflow's
        for probe, header in s["accepted_permissions"].items():
            allowed = s["matrix"][job][probe] in (200, 201)
            assert satisfies(perms, header) is allowed, (job, probe)
            cells += 1
    assert cells == 18

    assert effective(None, {"issues": "write"})["contents"] == "none"
    assert effective(None, {"issues": "write"})["issues"] == "write"
    assert set(effective(None, "write-all").values()) == {"write"}
    assert set(effective(None, {}).values()) == {"none"}
    dflt = effective(None, None)
    assert dflt["contents"] == "read" and dflt["issues"] == "none"
    d = s["default_workflow_run"]
    assert (d["tag"], d["label"], d["secrets"]) == (403, 403, 403)
    assert s["repo_settings"]["default_workflow_permissions"] == "read"

    assert s["matrix"]["write_all"]["secrets"] == 403           # never grantable
    assert not satisfies(effective(None, "write-all"), s["accepted_permissions"]["secrets"])
    assert s["error_message"] == "Resource not accessible by integration"
    assert s["token"] == {"prefix": "ghs_", "length": 377}

    rl = s["rate_limit"]
    assert rl["calls_ok"] == rl["calls_made"] == 1150 > rl["docs_limit"]
    assert rl["header_limit"] == 5000 and rl["calls_failed"] == 0
    assert rl["remaining_before"] - rl["remaining_after"] == 1069  # exercise 5

    wf = load_workflow(WORKFLOWS_DIR / "ch15-token-probes.yml")
    assert wf["jobs"]["none"]["permissions"] == {}
    assert wf["jobs"]["write_all"]["permissions"] == "write-all"
    assert "permissions" not in load_workflow(WORKFLOWS_DIR / "ch15-default-permissions.yml")
    print("18 matrix cells, default, never-grantable and rate-limit facts all asserted")


if __name__ == "__main__":
    main()
