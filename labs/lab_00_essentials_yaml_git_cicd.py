"""Lab 00: reproduce the two YAML traps and the Git ref model, offline.

Run: ``uv run python labs/lab_00_essentials_yaml_git_cicd.py``
Every number printed here is asserted, so the chapter's claims are checked by code.
"""

from __future__ import annotations

import yaml

from intro_gha import GHA_MODE
from intro_gha.workflow import load_workflow, triggers

TALLY_WORKFLOW = """
name: CI
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    steps:
      - uses: actions/checkout@v4
      - run: python -m pytest
"""

HISTORY = {"a1b2c3d": None, "e4f5a6b": "a1b2c3d", "9c8d7e6": "e4f5a6b"}


def trap_one_float_version() -> list[float]:
    """Show that an unquoted ``3.10`` parses to the float 3.1."""
    doc = yaml.safe_load(TALLY_WORKFLOW)
    versions = doc["jobs"]["test"]["strategy"]["matrix"]["python-version"]
    assert versions == [3.9, 3.1, 3.11]
    quoted = yaml.safe_load("v: ['3.9', '3.10', '3.11']")["v"]
    assert quoted == ["3.9", "3.10", "3.11"]
    return versions


def trap_two_on_is_true() -> tuple[bool, bool]:
    """Show ``on`` parses to ``True`` raw, and to ``"on"`` after normalization."""
    raw = yaml.safe_load(TALLY_WORKFLOW)
    raw_has_true = True in raw and "on" not in raw
    normalized = load_workflow_from_text(TALLY_WORKFLOW)
    assert triggers(normalized) == {"push": {}}
    return raw_has_true, "on" in normalized


def load_workflow_from_text(text: str) -> dict:
    """Normalize workflow text the way ``load_workflow`` does for files."""
    data = yaml.safe_load(text)
    if True in data:
        data["on"] = data.pop(True)
    return data


def ancestors(sha: str) -> list[str]:
    """Walk parent pointers from ``sha`` back to the root commit."""
    chain = [sha]
    while HISTORY[chain[-1]] is not None:
        chain.append(HISTORY[chain[-1]])
    return chain


def main() -> None:
    """Run every demonstration and print the results."""
    print("mode:", GHA_MODE)
    print("trap 1, parsed versions:", trap_one_float_version())
    print("trap 2, raw has True key / normalized has 'on':", trap_two_on_is_true())
    assert ancestors("9c8d7e6") == ["9c8d7e6", "e4f5a6b", "a1b2c3d"]
    print("history walk:", " <- ".join(reversed(ancestors("9c8d7e6"))))
    assert callable(load_workflow)


if __name__ == "__main__":
    main()
