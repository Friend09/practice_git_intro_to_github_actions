"""Validate the example workflow template against the documented structure."""

from __future__ import annotations

import json

import yaml

from intro_gha import REPO_ROOT

DIR = REPO_ROOT / "examples" / "workflow-templates"


def test_template_has_required_properties() -> None:
    """A template needs a same-named .properties.json with name and description."""
    props = json.loads((DIR / "tally-ci.properties.json").read_text())
    assert props["name"] and props["description"]
    assert (DIR / "tally-ci.yml").exists()


def test_template_uses_the_default_branch_placeholder() -> None:
    """$default-branch is replaced with the repository's real default branch."""
    text = (DIR / "tally-ci.yml").read_text()
    assert text.count("$default-branch") == 2
    body = yaml.safe_load(text.replace("$default-branch", "main"))
    assert body["jobs"]["test"]["uses"].startswith("ORG/.github/.github/workflows/")
    assert body["permissions"] == {"contents": "read"}
