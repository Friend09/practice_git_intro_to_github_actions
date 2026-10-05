"""Every workflow file parses, sets permissions, and has jobs with a runner."""

from __future__ import annotations

import pytest

from intro_gha import WORKFLOWS_DIR
from intro_gha.workflow import load_workflow, triggers

FILES = sorted(WORKFLOWS_DIR.glob("*.yml"))


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_workflow_is_well_formed(path) -> None:
    """Parses, has a trigger, explicit permissions, and every job runs somewhere."""
    wf = load_workflow(path)
    assert triggers(wf), "no triggers"
    assert "permissions" in wf, "missing top-level permissions"
    for job_id, job in wf["jobs"].items():
        assert "runs-on" in job or "uses" in job, f"{job_id} has no runs-on/uses"
