"""Lab 11: coverage arithmetic, the gate rule, and the real CI runs.

Run: ``uv run python labs/lab_11_ci_for_python.py`` (offline; all values asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.cost import billed_minutes, run_cost_mills
from intro_gha.workflow import (
    jobs_missing_checkout_with_workflow_workdir,
    load_workflow,
)


def coverage_percent(statements: int, missed: int) -> float:
    """Coverage as pytest-cov computes it: executed statements over total."""
    return 100 * (statements - missed) / statements


def gate(lint: str, test: str) -> bool:
    """The ci-ok rule: pass only if every upstream result is exactly 'success'."""
    return lint == "success" and test == "success"


def main() -> None:
    """Assert every number quoted in Chapter 11."""
    s = json.loads((FIXTURES_DIR / "ci_ch11_summary.json").read_text())
    red = s["runs"]["red_gate"]["coverage"]
    assert round(coverage_percent(red["statements"], red["missed"]), 2) == red["percent"]
    assert red["percent"] < red["gate"] and round(red["percent"]) == 53
    assert coverage_percent(20, 3) == 85.0 and coverage_percent(17, 8) < 80 <= 85.0
    assert s["coverage_after_fix"] == 100

    assert gate("success", "success") and not gate("failure", "success")
    assert not gate("skipped", "success") and not gate("success", "cancelled")
    bad = s["runs"]["bad_lint"]
    assert bad["ci_ok_report"] == {"lint": "failure", "test": "success"}
    assert not gate(**bad["ci_ok_report"])
    assert {a["title"] for a in bad["annotations"]} == {"ruff (F401)", "ruff (E402)"}

    pythons = s["pythons"]
    assert pythons["3.12"].startswith("3.12.") and len(pythons) == 4
    assert "python-3.12.14-pip" in s["pip_cache_key_example"]
    saved_when_red = s["runs"]["red_gate"]["pip_cache_saved_by"]
    assert saved_when_red == ["lint"]  # failing test legs saved nothing
    assert set(s["cache_outcomes"]["37321351215"].values()) == {"hit"}

    cold, warm = s["install_seconds"]["cold"], s["install_seconds"]["warm"]
    assert max(cold[k] - warm[k] for k in cold) <= 1  # caching saved at most 1 s
    jobs = list(s["job_seconds"]["warm"].values()) + [8]
    assert all(billed_minutes(j) == 1 for j in jobs)
    six = [(15, "linux")] * 6
    assert run_cost_mills(six) == 36 and 1000 * 36 == 36_000  # exercise 5

    bug = json.loads((FIXTURES_DIR / "ci_ch11_defaults_bug.json").read_text())
    assert "No such file or directory" in bug["error"]
    wf = load_workflow(WORKFLOWS_DIR / "ch11-python-ci.yml")
    assert jobs_missing_checkout_with_workflow_workdir(wf) == []
    assert wf["jobs"]["test"]["strategy"]["matrix"]["python"] == [
        "3.11", "3.12", "3.13", "3.14"]
    assert wf["jobs"]["ci-ok"]["if"] == "${{ always() }}"
    print("coverage 52.94% -> 100%, gate rule, cache table and billing all asserted")


if __name__ == "__main__":
    main()
