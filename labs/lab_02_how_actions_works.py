"""Lab 02: derive waves, wall-clock and billing from a real run fixture.

Run: ``uv run python labs/lab_02_how_actions_works.py``. With ``GHA_MODE=live`` the
fixture is refreshed from run 37311041878 via ``gh run view``.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from intro_gha import FIXTURES_DIR, GHA_MODE, GHA_REPO
from intro_gha.cost import run_cost_mills, run_minutes
from intro_gha.workflow import execution_waves

FMT = "%Y-%m-%dT%H:%M:%SZ"
RUN_ID = 37311041878
NEEDS = {"lint": [], "test": [], "build": ["lint", "test"]}


def load_run(path: Path = FIXTURES_DIR / "run_ch02_anatomy.json") -> dict:
    """Load the run fixture, or fetch it live when ``GHA_MODE=live``."""
    if GHA_MODE == "live":
        out = subprocess.run(
            ["gh", "run", "view", str(RUN_ID), "-R", GHA_REPO, "--json",
             "event,headSha,conclusion,jobs"],
            check=True, capture_output=True, text=True,
        ).stdout
        raw = json.loads(out)
        return {
            "head_sha": raw["headSha"],
            "jobs": [{"name": j["name"], "started_at": j["startedAt"],
                      "completed_at": j["completedAt"]} for j in raw["jobs"]],
        }
    return json.loads(path.read_text())


def spans(run: dict) -> dict[str, tuple[datetime, datetime]]:
    """Map job name to (start, end) datetimes."""
    return {
        j["name"]: (datetime.strptime(j["started_at"], FMT),
                    datetime.strptime(j["completed_at"], FMT))
        for j in run["jobs"]
    }


def main() -> None:
    """Assert every number quoted in Chapter 02, Section 5."""
    run = load_run()
    t = spans(run)
    assert execution_waves(NEEDS) == [["lint", "test"], ["build"]]
    durations = {k: int((e - s).total_seconds()) for k, (s, e) in t.items()}
    assert durations == {"lint": 2, "test": 4, "build": 3}
    assert t["build"][0] >= max(t["lint"][1], t["test"][1])  # needs honored
    wall = max(e for _, e in t.values()) - min(s for s, _ in t.values())
    assert int(wall.total_seconds()) == 10
    jobs = [(d, "linux") for d in durations.values()]
    assert run_minutes(jobs) == 3 and run_cost_mills(jobs) == 18
    # exercise 5: A=30s, B=45s parallel, C=20s after both
    assert max(30, 45) + 20 == 65
    print("durations:", durations, "| wall-clock:", wall.seconds, "s | billed min: 3")


if __name__ == "__main__":
    main()
