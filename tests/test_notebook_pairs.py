"""Structural tests for notebook pairing: every lab_XX has a hollow practice_XX twin."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

NOTEBOOKS = Path(__file__).resolve().parents[1] / "notebooks"
LABS = sorted(NOTEBOOKS.glob("lab_*.ipynb"))


def _num(path: Path) -> int:
    """Chapter number from a notebook file name."""
    return int(path.stem.split("_")[1])


def test_every_lab_has_a_practice_twin_and_vice_versa() -> None:
    """Lab and practice number sets must be identical."""
    lab_nums = {_num(p) for p in NOTEBOOKS.glob("lab_*.ipynb")}
    practice_nums = {_num(p) for p in NOTEBOOKS.glob("practice_*.ipynb")}
    assert lab_nums == practice_nums


@pytest.mark.parametrize("lab", LABS, ids=lambda p: p.stem)
def test_practice_mirrors_reference(lab: Path) -> None:
    """Same cell count and types; practice code cells are empty."""
    practice = NOTEBOOKS / f"practice_{_num(lab):02d}.ipynb"
    ref = json.loads(lab.read_text())["cells"]
    pra = json.loads(practice.read_text())["cells"]
    assert len(ref) == len(pra)
    for r, p in zip(ref, pra, strict=True):
        assert r["cell_type"] == p["cell_type"]
        if p["cell_type"] == "code":
            assert p["source"] in ("", [])
