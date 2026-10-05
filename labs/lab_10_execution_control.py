"""Lab 10: matrix expansion, needs propagation, concurrency and timeouts.

Run: ``uv run python labs/lab_10_execution_control.py`` (offline; all asserted).
"""

from __future__ import annotations

import json
from datetime import datetime

from intro_gha import FIXTURES_DIR
from intro_gha.cost import billed_minutes, run_cost_mills
from intro_gha.matrix import expand_matrix
from intro_gha.workflow import execution_waves

FMT = "%Y-%m-%dT%H:%M:%SZ"


def needs_results(graph: dict[str, list[str]], failed: set[str]) -> dict[str, str]:
    """Job conclusions under the default rule: every need must have succeeded."""
    out: dict[str, str] = {}
    for job in graph:  # graph must be in topological order
        if job in failed:
            out[job] = "failure"
        elif any(out[n] != "success" for n in graph[job]):
            out[job] = "skipped"
        else:
            out[job] = "success"
    return out


def max_overlap(jobs: list[dict]) -> int:
    """Largest number of jobs running at the same instant (jobs that got runners)."""
    spans = [(datetime.strptime(j["started_at"], FMT),
              datetime.strptime(j["completed_at"], FMT)) for j in jobs if j["ran"]]
    return max(sum(s <= t < e for s, e in spans) for t, _ in spans)


def seconds(job: dict) -> int:
    """Duration of one job from its fixture timestamps."""
    return int((datetime.strptime(job["completed_at"], FMT)
                - datetime.strptime(job["started_at"], FMT)).total_seconds())


def main() -> None:
    """Assert every claim made in Chapter 10."""
    d = json.loads((FIXTURES_DIR / "exec_ch10_all.json").read_text())

    graph = {"a": [], "b": ["a"], "c": ["b"]}
    assert needs_results(graph, {"a"}) == {"a": "failure", "b": "skipped", "c": "skipped"}
    real = {j["name"]: j["conclusion"] for j in d["needs"]["jobs"]}
    assert (real["a"], real["b"], real["c"]) == ("failure", "skipped", "skipped")
    assert real["report_always"] == real["report_on_failure"] == "success"
    assert real["report_default"] == "skipped"
    assert execution_waves(graph) == [["a"], ["b"], ["c"]]

    legs = expand_matrix({**{k: v for k, v in d["matrix"]["definition"].items()
                             if k in ("os", "py", "exclude", "include")}})
    assert len(legs) == 6
    ff, nf = d["matrix"]["fail_fast_true"]["jobs"], d["matrix"]["fail_fast_false"]["jobs"]
    assert len(ff) == len(nf) == 6
    assert sum(j["ran"] for j in ff) == 4 and sum(j["ran"] for j in nf) == 6
    never = [j["name"] for j in ff if not j["ran"]]
    assert sorted(never) == ["leg (ubuntu-22.04, 3.13)", "leg (ubuntu-latest, 3.14)"]
    assert max_overlap(nf) == 2 <= d["matrix"]["definition"]["max_parallel"]
    mins = lambda js: sum(billed_minutes(seconds(j)) for j in js if j["ran"])  # noqa: E731
    assert (mins(ff), mins(nf)) == (4, 6)

    x = {r["tag"]: r["run"]["conclusion"] for r in d["concurrency"]["cancel_false"]["runs"]}
    y = {r["tag"]: r["run"]["conclusion"] for r in d["concurrency"]["cancel_true"]["runs"]}
    assert x == {"x1": "success", "x2": "cancelled", "x3": "success"}
    assert y == {"y1": "cancelled", "y2": "cancelled", "y3": "success"}
    y1 = d["concurrency"]["cancel_true"]["runs"][0]["jobs"][0]
    assert y1["conclusion"] == "cancelled" and all(
        s["conclusion"] == "success" for s in y1["steps"])  # cancelled but steps done
    assert not d["concurrency"]["cancel_false"]["runs"][1]["jobs"]  # x2 never ran

    t = d["timeouts"]
    jobs = {j["name"]: j for j in t["jobs"]}
    assert jobs["job_timeout"]["conclusion"] == "cancelled"
    assert seconds(jobs["job_timeout"]) == 90 > 60
    st = t["step_times"]["step_timeout_slow_step"]
    started, ended = (datetime.strptime(st[k], "%H:%M:%S") for k in ("started", "completed"))
    assert int((ended - started).total_seconds()) == 73

    assert 256 * 6 == 1536 and (200 * 256 - 2000) * 6 == 295_200
    assert run_cost_mills([(50, "linux"), (50, "windows"), (50, "macos")]) == 78
    print("matrix 6->5->6, fail-fast saves 2 legs, queue keeps newest; all asserted")


if __name__ == "__main__":
    main()
