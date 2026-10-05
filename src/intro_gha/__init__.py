"""intro_gha: offline helpers that let every chapter's mechanics be checked in code."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
GHA_MODE = os.environ.get("GHA_MODE", "fixture")
GHA_REPO = os.environ.get("GHA_REPO", "Friend09/practice_git_intro_to_github_actions")
GHA_OUTPUT_DIR = Path(os.environ.get("GHA_OUTPUT_DIR", REPO_ROOT / "output"))
