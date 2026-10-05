"""Validate the expression evaluator against results from real GitHub runs."""

from __future__ import annotations

import json
import re

import pytest

from intro_gha import FIXTURES_DIR, REPO_ROOT, WORKFLOWS_DIR
from intro_gha.expr import ExprError, evaluate, stringify

ECHO = re.compile(r'echo "REPORT (\w+)=\$\{\{ (.+) \}\}"$')


def _cases() -> list[tuple[str, str, dict, str, str]]:
    """Return (run_name, key, contexts, expression, observed) for every echo line."""
    text = (WORKFLOWS_DIR / "ch07-expressions.yml").read_text()
    matches = (ECHO.search(line.strip()) for line in text.splitlines())
    exprs = {m[1]: m[2] for m in matches if m}
    out = []
    for name, inputs in (("defaults", {"name": "", "flag": False}),
                         ("inputs", {"name": "Tally", "flag": True})):
        data = json.loads((FIXTURES_DIR / f"ctx_ch07_{name}.json").read_text())
        ctx = {
            "github": {"event_name": "workflow_dispatch", "ref_name": "main",
                       "event": {"pull_request": {"title": None}}},
            "runner": {"os": "Linux"},
            "env": {"FLAG_TEXT": "false", "ZERO_TEXT": "0", "EMPTY": ""},
            "inputs": inputs,
            "job": {"status": "success"},
        }
        for job in ("literals",):
            for key, observed in data["reports"][job].items():
                if key in exprs:
                    out.append((name, key, ctx, exprs[key], observed))
    return out


CASES = _cases()


def test_cases_are_extracted() -> None:
    """The workflow yields a healthy number of single-expression echo lines."""
    assert len(CASES) >= 60  # ~35 expressions x 2 runs


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c[0]}-{c[1]}")
def test_matches_real_engine(case: tuple) -> None:
    """Our evaluator returns the exact string the real runner printed."""
    _, _, ctx, expr, observed = case
    assert stringify(evaluate(expr, ctx)) == observed


def test_no_arithmetic() -> None:
    """GitHub has no ``+``; so neither do we."""
    with pytest.raises(ExprError):
        evaluate("1 + 1", {})


def test_hashfiles_matches_real_run() -> None:
    """hashFiles on one file equals the value the runner computed."""
    data = json.loads((FIXTURES_DIR / "ctx_ch07_defaults.json").read_text())
    observed = data["reports"]["matrixed (3.10)"]["hash"]
    from intro_gha.expr import _hash_files

    assert _hash_files("sandbox/tally/tally/add.py", root=REPO_ROOT) == observed
