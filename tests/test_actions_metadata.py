"""Validate local actions against the metadata rules (docs verified 2026-10)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from intro_gha import REPO_ROOT
from intro_gha.semver import parse

ACTIONS = sorted((REPO_ROOT / ".github" / "actions").glob("*/action.yml"))
SH = REPO_ROOT / ".github" / "actions" / "tally-version" / "parse.sh"


@pytest.mark.parametrize("path", ACTIONS, ids=lambda p: p.parent.name)
def test_action_metadata_is_valid(path: Path) -> None:
    """Required keys exist and the runtime-specific rules hold."""
    meta = yaml.safe_load(path.read_text())
    assert meta["name"] and meta["description"]
    for kind in ("inputs", "outputs"):
        for key, spec in (meta.get(kind) or {}).items():
            assert spec.get("description"), f"{kind}.{key} needs a description"
    runs = meta["runs"]
    using = runs["using"]
    assert using in {"composite", "node24", "docker"}
    if using == "composite":
        for step in runs["steps"]:
            if "run" in step:
                assert "shell" in step, "composite run steps need a shell"
        for key, spec in (meta.get("outputs") or {}).items():
            assert "value" in spec, f"composite output {key} needs a value"
    if using == "node24":
        assert (path.parent / runs["main"]).exists()
        if "post" in runs:
            assert (path.parent / runs["post"]).exists()
    if using == "docker":
        image = runs["image"]
        assert image.startswith("docker://") or (path.parent / image).exists()


def _run_script(version: str, tmp_path: Path) -> tuple[int, dict[str, str]]:
    """Run parse.sh with VERSION set; return (exit code, parsed outputs)."""
    out = tmp_path / "out.txt"
    out.write_text("")
    res = subprocess.run(
        ["bash", str(SH)],
        env={"VERSION": version, "GITHUB_OUTPUT": str(out), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True,
    )
    pairs = [line.split("=", 1) for line in out.read_text().splitlines() if "=" in line]
    return res.returncode, dict(pairs)


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("version", ["0.1.0", "1.2.3-rc.1", "10.20.30", "2.0.0-beta"])
def test_script_accepts_what_semver_accepts(version: str, tmp_path: Path) -> None:
    """The shell regex and the Python parser agree on valid versions."""
    code, outputs = _run_script(version, tmp_path)
    v = parse(version)
    assert code == 0
    assert (outputs["major"], outputs["minor"], outputs["patch"]) == (
        str(v.major), str(v.minor), str(v.patch))
    assert outputs["is_prerelease"] == ("true" if v.pre else "false")


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
@pytest.mark.parametrize("version", ["1.2", "v1.2.3", "01.2.3", "1.2.3.4", ""])
def test_script_rejects_what_semver_rejects(version: str, tmp_path: Path) -> None:
    """Invalid versions exit non-zero and write no outputs."""
    code, outputs = _run_script(version, tmp_path)
    assert code != 0 and outputs == {}
    with pytest.raises(ValueError):
        parse(version)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_node_unit_tests_pass() -> None:
    """The JavaScript action's own unit tests pass under node --test."""
    test_dir = REPO_ROOT / ".github" / "actions" / "tally-js" / "test"
    res = subprocess.run(
        ["node", "--test", str(test_dir)], capture_output=True, text=True
    )
    assert res.returncode == 0, res.stdout[-400:]
