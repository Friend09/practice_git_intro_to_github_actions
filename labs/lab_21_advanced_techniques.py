"""Lab 21: dynamic matrices, github-script and ChatOps, asserted from real runs.

Run: ``uv run python labs/lab_21_advanced_techniques.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.workflow import load_workflow

ALLOWED = {"OWNER", "MEMBER", "COLLABORATOR"}


def validate_plan(matrix_json: str) -> list[dict]:
    """Return the legs of a plan, raising unless it has a non-empty ``include`` list."""
    legs = json.loads(matrix_json)["include"]
    if not isinstance(legs, list) or not legs:
        raise ValueError("matrix must contain at least one leg")
    return legs


def guarded_outcome(count: int) -> str:
    """Model ``if: count > 0`` on the matrix job."""
    return "runs" if count > 0 else "skipped"


def handle(body: str, association: str) -> tuple[str, str]:
    """Return ``(outcome, reply)`` for a ChatOps comment, as the workflow script does."""
    _, sub, *rest = body.split()
    if association not in ALLOWED:
        return "denied", f"Not authorized ({association})."
    if sub == "ping":
        return "ping", "pong"
    if sub == "echo":
        return "echo", " ".join(rest) or "(nothing to echo)"
    return "help", "Commands: /tally ping, /tally echo <text>"


def main() -> None:
    """Assert every claim made in Chapter 21."""
    s = json.loads((FIXTURES_DIR / "advanced_ch21_summary.json").read_text())

    dm = s["dynamic_matrix"]
    assert dm["unguarded"]["valid"]["conclusion"] == "success"
    assert len(dm["unguarded"]["valid"]["jobs"]) == 4            # plan + 3 legs
    for mode in ("invalid", "empty"):
        assert dm["unguarded"][mode]["conclusion"] == "failure"
        assert dm["unguarded"][mode]["jobs"] == ["plan"]
        assert not dm["unguarded"][mode]["run_job_present"]
    g = dm["guarded_by_count"]
    assert g["valid"]["legs"] == 3 and g["valid"]["conclusion"] == "success"
    for mode in ("invalid", "empty"):                            # the guard hides the failure
        assert g[mode]["run_job"] == "skipped" and g[mode]["conclusion"] == "success"
    assert g["invalid"]["count_output"] == ""                    # not -1: jq cannot try a parse error
    fe = dm["fromjson_empty"]
    assert fe["step_level"]["conclusion"] == "failure"
    assert fe["job_level_if"]["conclusion"] == "skipped"

    legs = validate_plan(dm["plan_report_valid"])
    assert [f"run ({x['name']}, {x['python']})" for x in legs] == [
        j for j in dm["unguarded"]["valid"]["jobs"] if j != "plan"
    ]
    for bad in ("this is not json", '{"include":[]}'):
        try:
            validate_plan(bad)
            raise AssertionError(bad)
        except (ValueError, KeyError):
            pass
    assert guarded_outcome(3) == "runs" and guarded_outcome(0) == "skipped"

    gs = s["github_script"]
    assert gs["created"]["action"] == "created" and gs["updated"]["action"] == "updated"
    assert gs["comments_on_pr"] == 1 and gs["title_printed_literally"]
    assert gs["result_collision"]["setOutput_result_value_seen"] == ""
    assert gs["result_collision"]["fixed_value"] == "outcome=ping"

    co = s["chatops"]
    assert len(co["runs"]) == 5
    assert [r["job"] for r in co["runs"]].count("skipped") == 2
    assert co["bot_replies_started_runs"] == 0
    assert (co["owner_author_association"], co["bot_author_association"]) == ("OWNER", "NONE")
    assert set(co["allowed_associations"]) == ALLOWED
    assert handle("/tally echo hello    from   chatops", "OWNER") == ("echo", co["echo_output"])
    assert handle("/tally ping", "OWNER") == ("ping", "pong")
    assert handle("/tally ping", "CONTRIBUTOR") == ("denied", "Not authorized (CONTRIBUTOR).")
    assert handle("/tally nonsense", "OWNER")[0] == "help"

    for name in ("ch21-dynamic-matrix", "ch21-github-script", "ch21-chatops"):
        assert "permissions" in load_workflow(WORKFLOWS_DIR / f"{name}.yml")
    print("dynamic matrix, github-script and ChatOps claims all asserted")


if __name__ == "__main__":
    main()
