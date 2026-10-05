"""Load workflow YAML and answer structural questions about it.

Workflow YAML has a trap: PyYAML parses the bare key ``on`` as boolean ``True``
(YAML 1.1). ``load_workflow`` normalizes it back to the string ``"on"``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_workflow(path: Path) -> dict[str, Any]:
    """Parse a workflow file, mapping the YAML-1.1 boolean key ``True`` to ``"on"``."""
    data = yaml.safe_load(path.read_text())
    if True in data:
        data["on"] = data.pop(True)
    return data


def triggers(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the ``on:`` block as ``{event: config}`` whatever its source form.

    ``on: push``, ``on: [push, pull_request]`` and ``on: {push: {...}}`` all work.
    """
    raw = workflow.get("on", {})
    if isinstance(raw, str):
        return {raw: {}}
    if isinstance(raw, list):
        return {event: {} for event in raw}
    return {event: (cfg or {}) for event, cfg in raw.items()}


def job_ids(workflow: dict[str, Any]) -> list[str]:
    """Return job ids in declaration order."""
    return list(workflow.get("jobs", {}))


def job_graph(workflow: dict[str, Any]) -> dict[str, list[str]]:
    """Map each job id to the list of job ids it ``needs``."""
    graph: dict[str, list[str]] = {}
    for job_id, job in workflow.get("jobs", {}).items():
        needs = job.get("needs", [])
        graph[job_id] = [needs] if isinstance(needs, str) else list(needs)
    return graph


def execution_waves(graph: dict[str, list[str]]) -> list[list[str]]:
    """Group jobs into waves that can run in parallel, honoring ``needs``.

    Raises ValueError on a dependency cycle or an unknown job reference.
    """
    remaining = dict(graph)
    done: set[str] = set()
    waves: list[list[str]] = []
    while remaining:
        ready = sorted(j for j, deps in remaining.items() if set(deps) <= done)
        if not ready:
            raise ValueError(f"cycle or unknown dependency among: {sorted(remaining)}")
        waves.append(ready)
        done.update(ready)
        for job in ready:
            del remaining[job]
    return waves
