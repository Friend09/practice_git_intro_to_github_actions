"""Injection checker tests, including the real command line from run 37327434888."""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.injection import injection_sites, interpolate, untrusted_expressions
from intro_gha.workflow import load_workflow

S = json.loads((FIXTURES_DIR / "security_ch16_summary.json").read_text())["injection"]
# These workflows interpolate dispatch inputs on purpose (Chapters 07 and 16).
INTENTIONAL = {"ch07-expressions.yml", "ch16-injection.yml"}


def test_interpolation_reproduces_the_real_command_line() -> None:
    """Substituting the payload gives exactly the line the runner executed."""
    script = 'echo "REPORT vulnerable_title=${{ inputs.title }}"'
    rendered = interpolate(script, {"inputs.title": S["payload"]})
    assert rendered == S["vulnerable"]["command_line_run"]


def test_safe_pattern_has_no_expression_in_the_script() -> None:
    """Passing through env leaves a plain shell variable in the script."""
    assert untrusted_expressions('echo "REPORT safe_title=$TITLE"') == []


def test_only_intentional_workflows_have_injection_sites() -> None:
    """Every other workflow passes untrusted values through env."""
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        sites = injection_sites(load_workflow(path))
        if path.name in INTENTIONAL:
            continue
        assert not sites, (path.name, sites)


def test_vulnerable_job_is_flagged_and_safe_job_is_not() -> None:
    """Static analysis agrees with the live experiment."""
    sites = injection_sites(load_workflow(WORKFLOWS_DIR / "ch16-injection.yml"))
    assert [s[0] for s in sites] == ["vulnerable"]
