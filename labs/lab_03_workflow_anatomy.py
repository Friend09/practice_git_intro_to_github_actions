"""Lab 03: parse the real workflow, test its paths filter, read green/red runs.

Run: ``uv run python labs/lab_03_workflow_anatomy.py`` (offline; all values asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.badge import badge_status, badge_url
from intro_gha.cost import run_cost_mills
from intro_gha.triggers import paths_trigger
from intro_gha.workflow import load_workflow, triggers


def conclusions(name: str) -> dict[str, str]:
    """Map step name to conclusion for a saved run fixture (green or red)."""
    run = json.loads((FIXTURES_DIR / f"run_ch03_{name}.json").read_text())
    return {s["name"]: s["conclusion"] for s in run["steps"]}


def main() -> None:
    """Assert every claim made in Chapter 03."""
    wf = load_workflow(WORKFLOWS_DIR / "ch03-tally-ci.yml")
    trig = triggers(wf)
    assert set(trig) == {"push", "workflow_dispatch"}
    paths = trig["push"]["paths"]
    assert paths_trigger(["sandbox/tally/tally/add.py"], paths)
    assert not paths_trigger(["README.md"], paths)
    assert not paths_trigger(["learning_modules/chapter_03_workflow_anatomy.md"], paths)
    assert paths_trigger(["README.md", "sandbox/tally/tests/test_add.py"], paths)
    assert wf["permissions"] == {"contents": "read"}
    assert wf["jobs"]["test"]["timeout-minutes"] == 5
    steps = wf["jobs"]["test"]["steps"]
    assert len(steps) == 5 and steps[3]["if"] == "${{ inputs.fail }}"

    green, red = conclusions("green"), conclusions("red")
    assert green["Break add() on purpose"] == "skipped"
    assert red["Break add() on purpose"] == "success"
    assert green["Run tests"] == "success" and red["Run tests"] == "failure"
    assert run_cost_mills([(14, "linux")]) == run_cost_mills([(16, "linux")]) == 6
    badges = json.loads((FIXTURES_DIR / "badge_ch03.json").read_text())
    statuses = {b["query"]: badge_status(f"<title>{b['title']}</title>") for b in badges["badges"]}
    assert statuses["?event=workflow_dispatch"] == "failing" and statuses[""] == "passing"
    assert badge_url(badges["repo"], badges["workflow_file"], event="workflow_dispatch").endswith(
        "ch03-tally-ci.yml/badge.svg?event=workflow_dispatch"
    )
    print("green:", green["Run tests"], "| red:", red["Run tests"], "| 6 mills each")


if __name__ == "__main__":
    main()
