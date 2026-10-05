"""Expand a ``strategy.matrix`` into concrete jobs, mirroring GitHub's algorithm."""

from __future__ import annotations

from itertools import product
from typing import Any

MAX_MATRIX_JOBS = 256


def expand_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the list of job combinations for a matrix definition.

    Cross product of every axis, minus ``exclude`` entries, plus ``include`` entries.
    An include whose keys do not overwrite an original axis value is added to every
    matching combination; one that matches none becomes its own job.
    """
    axes = {k: v for k, v in matrix.items() if k not in ("include", "exclude")}
    combos: list[dict[str, Any]] = (
        [dict(zip(axes, values, strict=True)) for values in product(*axes.values())]
        if axes
        else []
    )
    for ex in matrix.get("exclude", []):
        combos = [c for c in combos if not all(c.get(k) == v for k, v in ex.items())]
    for inc in matrix.get("include", []):
        matched = False
        for combo in combos:
            orig_keys = [k for k in inc if k in axes]
            if all(combo.get(k) == inc[k] for k in orig_keys):
                combo.update({k: v for k, v in inc.items() if k not in axes})
                matched = True
        if not matched:
            combos.append(dict(inc))
    return combos


def check_limit(combos: list[dict[str, Any]]) -> None:
    """Raise ValueError if the matrix exceeds GitHub's 256-job limit."""
    if len(combos) > MAX_MATRIX_JOBS:
        raise ValueError(f"matrix has {len(combos)} jobs; limit is {MAX_MATRIX_JOBS}")
