"""Lab 06: predict which workflows fire, evaluate cron, read real event dumps.

Run: ``uv run python labs/lab_06_events_and_triggers.py`` (offline; all asserted).
With ``GHA_MODE=live`` it also compares the model to the repo's most recent real runs.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime

from intro_gha import FIXTURES_DIR, GHA_MODE, GHA_REPO, WORKFLOWS_DIR
from intro_gha.cost import run_cost_mills
from intro_gha.events import next_cron_run, would_fire
from intro_gha.workflow import load_workflow

OBS = json.loads((FIXTURES_DIR / "events_ch06_observed.json").read_text())
WFS = {n: load_workflow(WORKFLOWS_DIR / n) for n in OBS["workflows"]}


def predict(observation: dict) -> list[str]:
    """Names of workflows the model says fire for one recorded experiment."""
    present = observation.get("workflows", OBS["workflows"])
    return sorted(n for n in present if would_fire(WFS[n], observation["event"]))


def live_check() -> None:
    """Print the repo's latest push runs so a reader can compare with the model."""
    out = subprocess.run(
        ["gh", "run", "list", "-R", GHA_REPO, "--limit", "10", "--json",
         "workflowName,event,headBranch"],
        check=True, capture_output=True, text=True,
    ).stdout
    for run in json.loads(out):
        print("live:", run["workflowName"], "|", run["event"], "|", run["headBranch"])


def main() -> None:
    """Assert every claim made in Chapter 06."""
    for obs in OBS["observations"]:
        assert predict(obs) == sorted(obs["fired"]), obs["id"]
    print(f"model matches all {len(OBS['observations'])} real experiments")

    d = OBS["event_dumps"]
    pr = d["pull_request"]
    assert pr["sha"] == pr["api_merge_commit_sha"] != pr["pr_head_sha"]
    assert pr["ref"] == "refs/pull/1/merge" and pr["base_ref"] == "main"
    wr = d["workflow_run"]
    assert wr["downstream_sha"] == wr["default_branch_head"] != wr["upstream_head_sha"]
    assert d["repository_dispatch"]["action"] == "tally-ping"

    start = datetime(2026, 10, 5, 12, 0)
    assert next_cron_run("23 4 1 1 *", start) == datetime(2027, 1, 1, 4, 23)
    assert next_cron_run("30 6 * * 1-5", start) == datetime(2026, 10, 6, 6, 30)
    assert next_cron_run("0 0 13 * 5", start) == datetime(2026, 10, 9, 0, 0)
    assert 12 * run_cost_mills([(40, "linux")] * 3) == 216  # exercise 5

    if GHA_MODE == "live":
        live_check()


if __name__ == "__main__":
    main()
