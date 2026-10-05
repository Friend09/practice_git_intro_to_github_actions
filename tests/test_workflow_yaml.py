"""Every workflow file parses, sets permissions, and has jobs with a runner."""

from __future__ import annotations

import pytest

from intro_gha import WORKFLOWS_DIR
from intro_gha.workflow import load_workflow, triggers

FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))
# Deliberately has no permissions block, to demonstrate the repository default (Ch 15).
NO_PERMISSIONS_OK = {"ch15-default-permissions.yml"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_workflow_is_well_formed(path) -> None:
    """Parses, has a trigger, explicit permissions, and every job runs somewhere."""
    wf = load_workflow(path)
    assert triggers(wf), "no triggers"
    if path.name not in NO_PERMISSIONS_OK:
        assert "permissions" in wf, "missing top-level permissions"
    for job_id, job in wf["jobs"].items():
        assert "runs-on" in job or "uses" in job, f"{job_id} has no runs-on/uses"


def test_no_workflow_workdir_trap() -> None:
    """No workflow applies a working-directory to a job that never checks out."""
    from intro_gha.workflow import jobs_missing_checkout_with_workflow_workdir

    for path in FILES:
        flagged = jobs_missing_checkout_with_workflow_workdir(load_workflow(path))
        assert not flagged, path


def test_workdir_trap_is_detected() -> None:
    """The buggy shape from run 37321351215 is flagged; the fixed shape is not."""
    from intro_gha.workflow import jobs_missing_checkout_with_workflow_workdir

    buggy = {
        "defaults": {"run": {"working-directory": "sandbox/tally"}},
        "jobs": {
            "test": {"steps": [{"uses": "actions/checkout@v7"}, {"run": "pytest"}]},
            "ci-ok": {"steps": [{"run": "true"}]},
        },
    }
    assert jobs_missing_checkout_with_workflow_workdir(buggy) == ["ci-ok"]
    buggy["jobs"]["ci-ok"]["defaults"] = {"run": {"working-directory": "."}}
    assert jobs_missing_checkout_with_workflow_workdir(buggy) == []


PIN_EXEMPT = {  # these teach unpinned or mis-pinned forms on purpose
    "ch04-uses-forms.yml", "ch04-bad-ref.yml", "ch16-sha-policy.yml",
}


def test_remote_actions_are_sha_pinned() -> None:
    """From Chapter 16 on, every remote action in this repo is pinned to a full SHA."""
    from intro_gha.pinning import unpinned

    for path in FILES:
        if path.name in PIN_EXEMPT:
            continue
        loose = unpinned(load_workflow(path))
        assert not loose, (path.name, loose)
