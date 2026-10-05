"""A teaching model of CI migration: GitLab CI to a workflow, Jenkins inventory.

This is **not** the GitHub Actions Importer. It converts only the constructs the
GitHub docs map one-to-one and reports everything else as a note for a human, which
is the shape of every real migration: a mechanical part and a reviewed part.
"""

from __future__ import annotations

import re
from typing import Any

GITLAB_RESERVED = {
    "stages", "default", "variables", "include", "workflow", "image", "cache",
    "services", "before_script", "after_script",
}

JENKINS_CONSTRUCTS = {
    "agent docker": r"agent\s*\{\s*docker",
    "environment": r"\benvironment\s*\{",
    "options timeout": r"\btimeout\s*\(",
    "stage": r"\bstage\s*\(",
    "sh step": r"\bsh\s+['\"]",
    "when": r"\bwhen\s*\{",
    "post": r"\bpost\s*\{",
    "parallel": r"\bparallel\s*\{",
    "credentials": r"\bcredentials\s*\(",
}

JENKINS_TO_ACTIONS = {
    "agent docker": "jobs.<id>.container (and runs-on)",
    "environment": "env",
    "options timeout": "jobs.<id>.timeout-minutes",
    "stage": "a job (stages run in order only through needs)",
    "sh step": "a run step",
    "when": "jobs.<id>.if",
    "post": "no keyword: a final job with if: always(), or failure() at job level",
    "parallel": "jobs run in parallel by default; a matrix for variations",
    "credentials": "secrets (and environments for protected ones)",
}


def gitlab_to_workflow(doc: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Convert a parsed ``.gitlab-ci.yml`` into ``(workflow, notes)``.

    Mapped mechanically: ``script`` to ``run``, ``image`` to ``container``, stage order
    to ``needs``, ``variables`` to ``env``. Everything else becomes a note.
    """
    notes: list[str] = []
    stages: list[str] = list(doc.get("stages", ["test"]))
    image = (doc.get("default") or {}).get("image") or doc.get("image")
    by_stage: dict[str, list[str]] = {s: [] for s in stages}
    jobs: dict[str, Any] = {}
    for name, spec in doc.items():
        is_job = isinstance(spec, dict) and "script" in spec
        if name in GITLAB_RESERVED or not is_job:
            continue
        stage = spec.get("stage", "test")
        by_stage.setdefault(stage, []).append(name)
        job: dict[str, Any] = {"runs-on": "ubuntu-latest"}
        if image:
            job["container"] = image
        if "tags" in spec:
            notes.append(f"{name}: tags {spec['tags']} dropped; pick a runner label")
        if "rules" in spec:
            notes.append(f"{name}: rules need a human to write the if: / on: filter")
        if "cache" in spec:
            notes.append(f"{name}: cache needs actions/cache")
        if "artifacts" in spec:
            notes.append(f"{name}: artifacts need actions/upload-artifact")
        scripts = spec["script"]
        job["steps"] = [{"uses": "actions/checkout"}] + [{"run": s} for s in scripts]
        jobs[name] = job
    previous: list[str] = []
    for stage in stages:
        for name in by_stage.get(stage, []):
            if previous:
                jobs[name]["needs"] = list(previous)
        previous = by_stage.get(stage, []) or previous
    workflow: dict[str, Any] = {"on": "workflow_dispatch", "jobs": jobs}
    if doc.get("variables"):
        workflow["env"] = dict(doc["variables"])
    return workflow, notes


def jenkins_inventory(text: str) -> dict[str, int]:
    """Count Declarative Pipeline constructs in a Jenkinsfile, like an audit would."""
    return {k: len(re.findall(p, text)) for k, p in JENKINS_CONSTRUCTS.items()}
