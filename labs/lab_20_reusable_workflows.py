"""Lab 20: what crosses a reusable-workflow boundary, from the real run.

Run: ``uv run python labs/lab_20_reusable_workflows.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.workflow import load_workflow


def main() -> None:
    """Assert every claim made in Chapter 20."""
    s = json.loads((FIXTURES_DIR / "reusable_ch20_summary.json").read_text())
    jobs = json.loads((FIXTURES_DIR / "reusable_ch20_run.json").read_text())["jobs"]

    assert len(s["job_names"]) == 8                     # exercise 5: jobs that ran
    assert len(s["job_names"]) * 6 == 48
    assert 4 * 3 == 12 and 12 * 6 == 72                 # exercise 4
    assert "call_local / build" in jobs and "consume_output" in jobs
    assert all(v["conclusion"] == "success" for v in jobs.values())

    seen = s["called_sees"]
    assert seen["github_workflow"] == "ch20 caller" and seen["event_name"] == "workflow_dispatch"
    assert seen["github_workflow_ref"].endswith("ch20-caller.yml@refs/heads/main")
    assert not seen["caller_env_visible"] and seen["repo_vars_visible"]
    assert jobs["call_local / build"]["reports"]["caller_env"] == "[]"
    assert jobs["call_local / build"]["reports"]["color"] == "blue"

    dflt = jobs["call_local / build"]["reports"]
    assert (dflt["python"], dflt["run_tests"]) == ("3.12", "true")        # defaults
    m = {n: v["reports"]["python"] for n, v in jobs.items() if n.startswith("call_matrix")}
    assert sorted(m.values()) == ["3.11", "3.12"]

    sec = {
        "none": jobs["call_local / build"]["reports"]["secret_len"],
        "inherit": jobs["call_inherit / build"]["reports"]["secret_len"],
        "explicit": jobs["call_explicit_secret / build"]["reports"]["secret_len"],
    }
    assert sec == {"none": "0", "inherit": "23", "explicit": "23"}
    assert jobs["consume_output"]["reports"]["consumed_output"] == "[hello Tally on python 3.12]"

    oidc = jobs["oidc_in_called_workflow / claims"]["reports"]
    assert oidc["oidc_job_workflow_ref"].endswith("ch20-reusable-oidc.yml@refs/heads/main")
    assert oidc["oidc_workflow_ref"].endswith("ch20-caller.yml@refs/heads/main")
    assert ":ref:refs/heads/main" in oidc["oidc_sub"]

    f = s["failures"]
    assert f["permission_elevation"]["conclusion"] == "startup_failure"
    assert not f["permission_elevation"]["actionlint_caught"]
    assert f["missing_required_input"]["actionlint_caught"] and f["missing_required_input"]["jobs"] == 0

    caller = load_workflow(WORKFLOWS_DIR / "ch20-caller.yml")
    assert caller["jobs"]["call_inherit"]["secrets"] == "inherit"
    assert "demo_secret" in caller["jobs"]["call_explicit_secret"]["secrets"]
    assert caller["jobs"]["oidc_in_called_workflow"]["permissions"]["id-token"] == "write"
    called = load_workflow(WORKFLOWS_DIR / "ch20-reusable.yml")
    wc = called["on"]["workflow_call"]
    assert wc["inputs"]["who"]["required"] and wc["inputs"]["run-tests"]["type"] == "boolean"
    assert "summary" in wc["outputs"]
    print("inputs, vars, env, secrets, outputs, OIDC claims and failures all asserted")


if __name__ == "__main__":
    main()
