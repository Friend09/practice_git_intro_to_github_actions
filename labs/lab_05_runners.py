"""Lab 05: compare measured runners to the docs, price the matrix, read failure runs.

Run: ``uv run python labs/lab_05_runners.py`` (offline; every figure is asserted).
"""

from __future__ import annotations

import json
from datetime import datetime

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.cost import job_cost_mills, run_cost_mills, run_minutes
from intro_gha.workflow import load_workflow

FMT = "%Y-%m-%dT%H:%M:%SZ"
OS_KEY = {"Linux": "linux", "Windows": "windows", "macOS": "macos"}


def seconds(job: dict) -> int:
    """Duration of one job from its fixture timestamps."""
    start = datetime.strptime(job["started_at"], FMT)
    end = datetime.strptime(job["completed_at"], FMT)
    return int((end - start).total_seconds())


def main() -> None:
    """Assert every number quoted in Chapter 05."""
    data = json.loads((FIXTURES_DIR / "run_ch05_runners.json").read_text())
    by_label = {j["label"]: j for j in data["jobs"]}
    docs = data["docs_public_specs"]
    for label, (cpu, gb) in docs.items():
        assert by_label[label]["cpu"] == cpu
        assert abs(by_label[label]["mem_mb"] / 1024 - gb) < 1  # within 1 GB
    assert by_label["macos-latest"]["arch"] == "ARM64"
    assert {j["environment"] for j in data["jobs"]} == {"github-hosted"}

    jobs = [(seconds(j), OS_KEY[j["os"]]) for j in data["jobs"]]
    assert sorted(s for s, _ in jobs) == [3, 3, 5, 8]
    assert run_minutes(jobs) == 4 and run_cost_mills(jobs) == 84
    macos_share = job_cost_mills(5, "macos") / run_cost_mills(jobs)
    assert round(macos_share * 100) == 74
    assert run_cost_mills([(s, o) for s, o in jobs if o != "macos"]) == 22

    guarded = data["guarded_job"]
    assert guarded["conclusion"] == "skipped"
    assert guarded["started_at"] == guarded["completed_at"]

    stuck = json.loads((FIXTURES_DIR / "run_ch05_no_runner.json").read_text())
    assert stuck["job_status"] == "queued" and stuck["job_runner_name"] is None
    assert stuck["docs_queue_limit_hours"] == 24

    invalid = json.loads(
        (FIXTURES_DIR / "run_invalid_workflow_syntax.json").read_text()
    )
    assert invalid["jobs"] == [] and invalid["workflowName"].endswith(".yml")

    wf = load_workflow(WORKFLOWS_DIR / "ch05-runners.yml")
    assert wf["jobs"]["self-hosted-guarded"]["runs-on"] == ["self-hosted", "linux"]
    assert run_cost_mills([(70, "linux")] * 3 + [(20, "windows")]) == 46  # exercise 5
    print("matrix price: 84 mills | macOS share: 74% | guarded job skipped")


if __name__ == "__main__":
    main()
