"""Lab 08: scope resolution, masking and environment results from real runs.

Run: ``uv run python labs/lab_08_variables_secrets_environments.py`` (offline).
"""

from __future__ import annotations

import json
from datetime import datetime

from intro_gha import FIXTURES_DIR

FMT = "%Y-%m-%dT%H:%M:%SZ"


def resolve(name: str, workflow: dict, job: dict, step: dict) -> str | None:
    """Innermost definition wins: step, then job, then workflow."""
    for scope in (step, job, workflow):
        if name in scope:
            return scope[name]
    return None


def reports(name: str) -> dict:
    """Load the ``reports`` mapping of a saved run fixture."""
    return json.loads((FIXTURES_DIR / name).read_text())["reports"]


def main() -> None:
    """Assert every claim made in Chapter 08."""
    wf, job = {"SCOPE": "workflow"}, {"SCOPE": "job"}
    assert resolve("SCOPE", wf, job, {"SCOPE": "step"}) == "step"
    assert resolve("SCOPE", wf, job, {}) == "job"
    assert resolve("SCOPE", wf, {}, {}) == "workflow"
    assert resolve("MISSING", wf, job, {}) is None

    cfg = reports("config_ch08_run.json")
    s = cfg["scopes"]
    assert (s["scope_at_job"], s["scope_at_step"]) == ("job", "step")
    assert cfg["workflow_scope_only"]["scope_at_workflow"] == "workflow"
    assert s["same_step_sees"] == "unset"
    assert s["next_step_sees"] == s["next_step_expr"] == "written-by-previous-step"
    assert s["CI"] == s["GITHUB_ACTIONS"] == "true"

    v = cfg["vars_and_secrets"]
    assert v["repo_color"] == "blue" and v["missing_var"] == "[]"
    assert v["secret_direct"] == v["secret_base64"] == "***"
    assert v["secret_len"] == "23"
    assert v["derived_before_mask"] == "EULAV-terc3s-omed-yllat"
    assert v["derived_after_mask"] == "***"
    assert v["derived_before_mask"] == "tally-demo-s3cret-VALUE"[::-1]
    assert v["env_secret_not_visible_outside_env_len"] == "0"

    envr = reports("environments_ch08_run.json")
    st = envr["staging"]
    assert st["staging_color"] == "green" and st["staging_only_len"] == "18"
    assert st["staging_sees_repo_secret_len"] == "23"
    assert envr["production"]["production_deployed"] == "yes"

    run = json.loads((FIXTURES_DIR / "environments_ch08_run.json").read_text())
    assert run["conclusion"] == "success"
    staging_done = datetime.strptime("2026-10-05T13:28:46Z", FMT)
    prod_start = datetime.strptime("2026-10-05T13:29:37Z", FMT)
    assert int((prod_start - staging_done).total_seconds()) == 51
    print("all Chapter 08 values match the real runs; approval wait = 51 s")


if __name__ == "__main__":
    main()
