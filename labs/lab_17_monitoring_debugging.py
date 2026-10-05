"""Lab 17: annotations, re-runs, debug traces, the didn't-run checklist and metrics.

Run: ``uv run python labs/lab_17_monitoring_debugging.py`` (offline; all asserted).
"""

from __future__ import annotations

import collections
import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.expr import evaluate, stringify
from intro_gha.workflow import execution_waves, load_workflow


def surfaced(emitted: int, cap: int = 10) -> int:
    """Annotations of one level that survive the per-step cap."""
    return min(emitted, cap)


def main() -> None:
    """Assert every claim made in Chapter 17."""
    s = json.loads((FIXTURES_DIR / "observability_ch17_summary.json").read_text())

    a = s["annotations"]
    assert surfaced(15) == a["surfaced"]["error"] == a["surfaced"]["warning"] == 10
    assert a["surfaced"]["notice"] == surfaced(15) + 1  # plus the platform's own notice
    assert surfaced(25) + surfaced(25) == 20  # exercise 1: per step, not per job
    assert a["two_steps_of_8_errors"]["total"] == 16 > 10

    rr = s["rerun"]
    assert rr["attempt2_via_rerun_failed"]["flaky"] == "success"
    assert rr["attempt2_via_rerun_failed"]["stable_attempt_value"] == 1
    assert not rr["attempt2_via_rerun_failed"]["commands_started_again"]
    assert rr["attempt2_via_rerun_failed"]["flaky_attempt_value"] == 2

    d = s["debug"]
    assert d["attempt1"]["debug_lines"] == 0 and d["attempt3_via_rerun_debug"]["debug_lines"] == 140
    assert d["attempt3_via_rerun_debug"]["total_lines"] - d["attempt1"]["total_lines"] == 146
    ctx = {"github": {"event_name": "workflow_dispatch"}}
    expr = "github.event_name == 'workflow_dispatch' && true"  # success() is true here
    assert stringify(evaluate(expr, ctx)) == "true"
    assert stringify(evaluate("'false' == 'true' && true", ctx)) == "false"  # exercise 3

    assert s["disabled"]["state"] == "disabled_manually"
    assert "disabled workflow" in s["disabled"]["dispatch_error"]

    graph = {"a": [], "b": ["a"], "c": ["b"], "report_always": ["a", "b", "c"],
             "report_on_failure": ["a", "b", "c"], "report_default": ["a"]}
    waves = execution_waves(graph)
    assert {str(i): w for i, w in enumerate(waves)} == s["act"]["list_stages"]

    snap = json.loads((FIXTURES_DIR / "runs_ch17_snapshot.json").read_text())
    runs = snap["runs"]
    c = collections.Counter(r["conclusion"] for r in runs)
    assert snap["count"] == len(runs) == 178 and c["success"] == 146
    assert round(100 * c["success"] / len(runs), 1) == 82.0
    assert len({r["workflow"] for r in runs}) == 40
    ci = [r for r in runs if r["workflow"] == "ci.yml"]
    ok = sum(r["conclusion"] == "success" for r in ci)
    assert (len(ci), ok) == (57, 46) and round(100 * ok / len(ci), 1) == 80.7

    fails = json.loads((FIXTURES_DIR / "ci_failures_ch17.json").read_text())
    causes = collections.Counter(f["cause"] for f in fails)
    assert len(fails) == len(ci) - ok == 11 and causes["ruff lint error"] == 8
    assert round(100 * 8 / 11, 1) == 72.7 and round(100 * (ok + 8) / len(ci), 1) == 94.7

    assert s["retention"] == {"days": 90, "maximum_allowed_days": 90}
    assert len(s["actionlint_catches_in_this_course"]) == 10
    wf = load_workflow(WORKFLOWS_DIR / "ch17-observability.yml")
    assert set(wf["jobs"]) == {"commands", "flaky", "stable", "annotation_scope"}
    print("annotation caps, re-run, debug trace, waves and CI-history metrics all asserted")


if __name__ == "__main__":
    main()
