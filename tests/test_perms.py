"""The permissions model, checked against the real probe matrix from run 37325286661."""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR
from intro_gha.perms import effective, satisfies

P = json.loads((FIXTURES_DIR / "token_ch15_summary.json").read_text())
JOB_PERMS = {
    "none": {},
    "contents_read": {"contents": "read"},
    "contents_write": {"contents": "write"},
    "issues_write": {"issues": "write"},
    "both_write": {"contents": "write", "issues": "write"},
    "write_all": "write-all",
}


def test_model_reproduces_the_real_matrix() -> None:
    """For every job and probe, predicted allow/deny equals the observed status."""
    for job, spec in JOB_PERMS.items():
        perms = effective({"contents": "read"}, spec)  # job overrides workflow
        for probe, accepted in P["accepted_permissions"].items():
            observed_ok = P["matrix"][job][probe] in (200, 201)
            assert satisfies(perms, accepted) is observed_ok, (job, probe)


def test_unspecified_scopes_become_none() -> None:
    """Setting only issues: write leaves contents at none."""
    assert effective(None, {"issues": "write"})["contents"] == "none"
    assert effective(None, {})["issues"] == "none"


def test_default_is_read_only() -> None:
    """With no permissions block anywhere the repository default (read) applies."""
    d = effective(None, None)
    assert d["contents"] == "read" and d["issues"] == "none"
    assert not satisfies(d, P["accepted_permissions"]["tag"])
    assert not satisfies(d, P["accepted_permissions"]["label"])


def test_write_includes_read_and_secrets_unreachable() -> None:
    """write covers read; the secrets scope is not a GITHUB_TOKEN permission at all."""
    assert satisfies({"contents": "write"}, "contents=read")
    assert not satisfies(effective(None, "write-all"), "secrets=read")
