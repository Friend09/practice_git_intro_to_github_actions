"""The migration model: stages become needs; unmapped constructs are reported."""

from __future__ import annotations

import yaml

from intro_gha import REPO_ROOT
from intro_gha.migrate import JENKINS_TO_ACTIONS, gitlab_to_workflow, jenkins_inventory
from intro_gha.workflow import execution_waves

SRC = REPO_ROOT / "sandbox" / "ch22"


def test_gitlab_stages_become_needs() -> None:
    """lint, test, deploy stages give three sequential waves."""
    wf, _ = gitlab_to_workflow(yaml.safe_load((SRC / "gitlab-ci.yml").read_text()))
    graph = {j: spec.get("needs", []) for j, spec in wf["jobs"].items()}
    assert execution_waves(graph) == [["lint"], ["test"], ["deploy"]]
    assert wf["jobs"]["lint"]["container"] == "python:3.12-slim"
    assert wf["env"] == {"TALLY_COLOR": "blue"}


def test_unmapped_constructs_are_reported() -> None:
    """tags, rules, cache and artifacts are never silently dropped."""
    _, notes = gitlab_to_workflow(yaml.safe_load((SRC / "gitlab-ci.yml").read_text()))
    text = "\n".join(notes)
    for needle in ("tags", "rules", "cache", "artifacts"):
        assert needle in text


def test_jenkins_inventory_covers_the_map() -> None:
    """Every counted Jenkins construct has a documented Actions counterpart."""
    inv = jenkins_inventory((SRC / "Jenkinsfile").read_text())
    assert inv["stage"] == 3 and inv["post"] == 1 and inv["when"] == 1
    assert inv["agent docker"] == 1 and inv["sh step"] == 3
    assert set(inv) == set(JENKINS_TO_ACTIONS)
