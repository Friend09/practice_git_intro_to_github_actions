"""Structural tests for chapter markdown files.

Wraps the git-independent checks from ``scripts/validate_chapters.py`` so CI
enforces header blocks, link/anchor integrity (which covers TOC coverage),
one-line ``$$`` math blocks, and artifact references. The heading-drift check
needs git history and stays in the manually-run script.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_chapters import (  # noqa: E402
    CHAPTERS_DIR,
    check_artifact_refs,
    check_header_block,
    check_links,
    check_math_blocks,
)

CHAPTER_PATHS = sorted(CHAPTERS_DIR.glob("chapter_*.md"))


@pytest.mark.parametrize("path", CHAPTER_PATHS, ids=lambda p: p.stem)
def test_chapter_structure(path: Path) -> None:
    """Every chapter passes the git-independent structural checks."""

    errors: list[str] = []
    text = path.read_text()
    check_header_block(text, errors)
    check_links(path, text, errors)
    check_math_blocks(text, errors)
    check_artifact_refs(path, text, errors)
    assert not errors, "\n".join(errors)
