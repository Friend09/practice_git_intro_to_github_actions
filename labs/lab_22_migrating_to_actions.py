"""Lab 22: migrating a pipeline, asserted from real runs and the migration model.

Run: ``uv run python labs/lab_22_migrating_to_actions.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

import yaml

from intro_gha import FIXTURES_DIR, REPO_ROOT, WORKFLOWS_DIR
from intro_gha.cost import billed_minutes
from intro_gha.migrate import JENKINS_TO_ACTIONS, gitlab_to_workflow, jenkins_inventory
from intro_gha.workflow import execution_waves, load_workflow


def main() -> None:
    """Assert every claim made in Chapter 22."""
    s = json.loads((FIXTURES_DIR / "migrating_ch22_summary.json").read_text())
    src = REPO_ROOT / "sandbox" / "ch22"

    # Stage order becomes needs (Section 4).
    wf, notes = gitlab_to_workflow(yaml.safe_load((src / "gitlab-ci.yml").read_text()))
    graph = {j: spec.get("needs", []) for j, spec in wf["jobs"].items()}
    assert execution_waves(graph) == [["lint"], ["test"], ["deploy"]]
    assert execution_waves({j: [] for j in graph}) == [["deploy", "lint", "test"]]
    assert all(any(k in n for n in notes) for k in ("tags", "rules", "cache", "artifacts"))

    # Jenkins inventory and the concept map (Section 10).
    inv = jenkins_inventory((src / "Jenkinsfile").read_text())
    assert (inv["stage"], inv["sh step"], inv["when"], inv["post"]) == (3, 3, 1, 1)
    assert set(inv) == set(JENKINS_TO_ACTIONS)

    # Real runs of the translated workflow (Section 6).
    assert s["ok_run"]["jobs"] == dict.fromkeys(("lint", "test", "deploy", "post"), "success")
    assert s["ok_run"]["post_report"]["test"] == "success"
    f = s["fail_run"]
    assert f["jobs"]["test"] == "failure" and f["jobs"]["deploy"] == "skipped"
    assert f["jobs"]["post"] == "success"                  # post-always equivalent ran
    assert f["post_report"] == {
        "post": "always", "lint": "success", "test": "failure", "deploy": "skipped",
    }
    assert f["post_job_step_level_failure_step"] == "skipped"
    assert f["job_level_failure_job"] == "success"
    assert not s["importer"]["installed_here"] and not s["importer"]["run_here"]

    # The workflow file matches what the chapter says.
    tw = load_workflow(WORKFLOWS_DIR / "ch22-translated.yml")
    assert tw["jobs"]["test"]["needs"] == ["lint"] and tw["jobs"]["deploy"]["needs"] == ["test"]
    assert tw["jobs"]["post"]["if"] == "${{ always() }}"
    assert tw["jobs"]["on_failure"]["if"] == "${{ failure() }}"
    assert tw["jobs"]["lint"]["container"] == "python:3.12-slim"

    # Exercise 5 and the cost section.
    stages = [20, 30, 15, 25]
    assert sum(billed_minutes(x) for x in stages) == 4 and billed_minutes(sum(stages)) == 2
    assert 4 * 6 == 24 and 2 * 6 == 12                      # mills at $0.006 per minute
    print("stage order, post-always, failure() scope, importer docs and cost all asserted")


if __name__ == "__main__":
    main()
