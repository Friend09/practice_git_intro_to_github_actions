"""Build a ``lab_XX`` reference notebook and its hollow ``practice_XX`` twin."""

from __future__ import annotations

import json

from intro_gha import REPO_ROOT
from intro_gha.chapters import CHAPTERS, chapter_stem

Cell = tuple[str, str]  # ("md" | "code", source)

SETUP = '''import os, sys
from pathlib import Path

ROOT = Path.cwd().resolve()
while not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

GHA_MODE = os.environ.get("GHA_MODE", "fixture")  # "fixture" | "live"
GHA_REPO = os.environ.get("GHA_REPO", "Friend09/practice_git_intro_to_github_actions")
print("mode:", GHA_MODE, "| repo:", GHA_REPO)'''


def _cell(kind: str, src: str, empty: bool) -> dict:
    """Return one nbformat-4 cell; code cells are blanked when ``empty``."""
    if kind == "md":
        return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(True)}
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": [] if empty else src.splitlines(True),
    }


def write_pair(num: int, cells: list[Cell], objectives: list[str]) -> None:
    """Write ``lab_XX_<slug>.ipynb`` and ``practice_XX.ipynb`` for chapter ``num``."""
    chapter = next(c for c in CHAPTERS if c.num == num)
    stem = chapter_stem(chapter)
    head: list[Cell] = [
        ("md", f"# Chapter {num:02d}: {chapter.title} (notebook edition)"),
        ("md", "## Learning Objectives\n\n" + "\n".join(f"- {o}" for o in objectives)),
        ("code", SETUP),
    ]
    tail: list[Cell] = [
        ("md", f"## Chapter Link\n\nRead: `learning_modules/chapter_{stem}.md`"),
    ]
    allcells = head + cells + tail
    for name, empty in ((f"lab_{stem}", False), (f"practice_{num:02d}", True)):
        nb = {
            "cells": [_cell(k, s, empty) for k, s in allcells],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        path = REPO_ROOT / "notebooks" / f"{name}.ipynb"
        path.write_text(json.dumps(nb, indent=1) + "\n")
