"""Static check for script-injection sites in workflow ``run:`` steps (Chapter 16).

GitHub evaluates ``${{ ... }}`` *before* the shell sees the script (Chapter 07), so
an expression an outsider controls becomes code. ``interpolate`` reproduces the
runner's substitution; ``injection_sites`` finds ``run:`` scripts that interpolate a
context an outsider can influence. The safe pattern: pass the value through ``env:``.
"""

from __future__ import annotations

import re
from typing import Any

EXPR_RE = re.compile(r"\$\{\{\s*(.+?)\s*\}\}")
UNTRUSTED_PREFIXES = (
    "github.event.issue.", "github.event.pull_request.", "github.event.comment.",
    "github.event.review.", "github.event.head_commit.", "github.event.commits",
    "github.event.workflow_run.", "github.event.pages", "github.head_ref", "inputs.",
)


def interpolate(script: str, values: dict[str, str]) -> str:
    """Replace each ``${{ name }}`` with ``values[name]`` as the runner does."""
    return EXPR_RE.sub(lambda m: values.get(m.group(1), ""), script)


def untrusted_expressions(script: str) -> list[str]:
    """Expressions in ``script`` that reference an outsider-influenced context."""
    return [
        e for e in EXPR_RE.findall(script)
        if any(p in e for p in UNTRUSTED_PREFIXES)
    ]


def step_scripts(step: dict[str, Any]) -> list[str]:
    """Script text a step executes: its ``run:`` and a github-script ``with.script``."""
    scripts = [step.get("run", "")]
    if str(step.get("uses", "")).startswith("actions/github-script@"):
        scripts.append(str(step.get("with", {}).get("script", "")))
    return scripts


def injection_sites(workflow: dict[str, Any]) -> list[tuple[str, int, str]]:
    """Return ``(job_id, step_index, expression)`` for each unsafe interpolation.

    Scans ``run:`` scripts and the ``script:`` input of ``actions/github-script``.
    """
    sites = []
    for job_id, job in workflow.get("jobs", {}).items():
        for i, step in enumerate(job.get("steps", [])):
            for script in step_scripts(step):
                for expr in untrusted_expressions(script):
                    sites.append((job_id, i, expr))
    return sites
