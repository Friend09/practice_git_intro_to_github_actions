"""Lab 07: replay the real engine's expression results with our evaluator.

Run: ``uv run python labs/lab_07_contexts_expressions.py`` (offline; all asserted).
"""

from __future__ import annotations

import json
import re

from intro_gha import FIXTURES_DIR, REPO_ROOT, WORKFLOWS_DIR
from intro_gha.expr import ExprError, _hash_files, evaluate, stringify

ECHO = re.compile(r'echo "REPORT (\w+)=\$\{\{ (.+) \}\}"$')
RUNS = {
    "defaults": {"name": "", "flag": False},
    "inputs": {"name": "Tally", "flag": True},
}


def contexts(inputs: dict) -> dict:
    """The contexts the real run had (dispatch event, Linux, our env block)."""
    return {
        "github": {"event_name": "workflow_dispatch", "ref_name": "main",
                   "event": {"pull_request": {"title": None}}},
        "runner": {"os": "Linux"},
        "env": {"FLAG_TEXT": "false", "ZERO_TEXT": "0", "EMPTY": ""},
        "inputs": inputs,
        "job": {"status": "success"},
    }


def expressions() -> dict[str, str]:
    """Extract ``{key: expression}`` for each single-expression echo line."""
    text = (WORKFLOWS_DIR / "ch07-expressions.yml").read_text()
    found = (ECHO.search(line.strip()) for line in text.splitlines())
    return {m[1]: m[2] for m in found if m}


def main() -> None:
    """Assert every claim made in Chapter 07."""
    exprs = expressions()
    checked = 0
    for run, inputs in RUNS.items():
        data = json.loads((FIXTURES_DIR / f"ctx_ch07_{run}.json").read_text())
        ctx = contexts(inputs)
        for key, observed in data["reports"]["literals"].items():
            if key in exprs:
                assert stringify(evaluate(exprs[key], ctx)) == observed, (run, key)
                checked += 1
    assert checked == 64
    print(f"evaluator reproduces {checked} real engine results")

    ctx = contexts(RUNS["defaults"])
    assert stringify(evaluate("'9' > '10'", ctx)) == "true"
    assert stringify(evaluate("9 > '10'", ctx)) == "false"
    assert stringify(evaluate("'ABC' == 'abc'", ctx)) == "true"
    assert stringify(evaluate("null == 0", ctx)) == "true"
    assert stringify(evaluate("'3.10' > '3.9'", ctx)) == "false"
    fmt = evaluate("format('{0}/{1}@{0}', 'tally', 'v7')", ctx)
    assert stringify(fmt) == "tally/v7@tally"
    assert stringify(evaluate("join(fromJSON('[1,2,3]'), '-')", ctx)) == "1-2-3"
    try:
        evaluate("1 + 1", ctx)
    except ExprError:
        print("no arithmetic: ExprError, as on GitHub")
    else:
        raise AssertionError("arithmetic should be rejected")

    observed = json.loads((FIXTURES_DIR / "ctx_ch07_defaults.json").read_text())
    real_hash = observed["reports"]["matrixed (3.10)"]["hash"]
    assert _hash_files("sandbox/tally/tally/add.py", root=REPO_ROOT) == real_hash
    status = observed["reports"]["status"]
    pair = (status["flaky_outcome"], status["flaky_conclusion"])
    assert pair == ("failure", "success")
    assert "failure_step_ran" not in status and status["always_step_ran"] == "yes"
    print("hashFiles and status results match the real runs")


if __name__ == "__main__":
    main()
