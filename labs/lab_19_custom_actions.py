"""Lab 19: run the composite script, validate action metadata, read the real run.

Run: ``uv run python labs/lab_19_custom_actions.py`` (offline; all asserted).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

from intro_gha import FIXTURES_DIR, REPO_ROOT, WORKFLOWS_DIR
from intro_gha.semver import parse
from intro_gha.workflow import load_workflow

ACTIONS = REPO_ROOT / ".github" / "actions"
SCRIPT = ACTIONS / "tally-version" / "parse.sh"


def run_script(version: str) -> tuple[int, dict[str, str]]:
    """Run parse.sh as the runner would; return (exit code, outputs)."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out.txt"
        out.write_text("")
        res = subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True,
            env={"VERSION": version, "GITHUB_OUTPUT": str(out), "PATH": "/usr/bin:/bin"},
        )
        pairs = [ln.split("=", 1) for ln in out.read_text().splitlines() if "=" in ln]
        return res.returncode, dict(pairs)


def metadata(name: str) -> dict:
    """Parse one action's action.yml."""
    return yaml.safe_load((ACTIONS / name / "action.yml").read_text())


def main() -> None:
    """Assert every claim made in Chapter 19."""
    s = json.loads((FIXTURES_DIR / "actions_ch19_summary.json").read_text())
    run = json.loads((FIXTURES_DIR / "actions_ch19_run.json").read_text())["reports"]

    valid = ["0.1.0", "1.2.3-rc.1", "10.20.30", "2.0.0-beta"]
    invalid = ["1.2", "v1.2.3", "01.2.3", "1.2.3.4", ""]
    for v in valid:
        code, out = run_script(v)
        p = parse(v)
        assert code == 0 and out["major"] == str(p.major) and out["normalized"] == v
    for v in invalid:
        code, out = run_script(v)
        assert code != 0 and out == {}
    assert len(valid) + len(invalid) + 3 + 2 == 14  # exercise 5

    comp = run["composite"]
    assert comp["composite_normalized"] == "1.2.3-rc.1" and comp["parts"] == "1.2.3"
    assert comp["bad_outcome"] == "failure" and comp["bad_normalized"] == "[]"
    assert run["remote_reference"]["remote_ref_parts"] == "3.4.5"

    js = run["javascript"]
    assert js["js_greeting"] == "HELLO, TALLY" and js["js_node"].startswith("v24.")
    assert js["js_inputs"] == "INPUT_SHOUT,INPUT_WHO-TO-GREET"
    assert js["js_post_ran"] == "yes" and js["state_started_present"] == "yes"
    assert run["javascript_post_after_failure"]["js_post_ran"] == "yes"
    assert s["javascript"]["post_after_failure"]["post_step_conclusion"] == "success"
    assert s["docker"]["built"]["step_seconds"] > s["docker"]["prebuilt"]["step_seconds"]
    assert 40 * 200 == 8000  # exercise 4
    assert run["docker_built"]["os"] == "alpine" and run["docker_prebuilt"]["prebuilt_action"] == "ran"

    for name in ("tally-version", "tally-js", "tally-docker", "tally-docker-prebuilt"):
        meta = metadata(name)
        assert meta["runs"]["using"] in {"composite", "node24", "docker"}
    comp_meta = metadata("tally-version")
    assert all("shell" in st for st in comp_meta["runs"]["steps"] if "run" in st)
    broken = metadata("tally-noshell")  # invalid on purpose
    assert any("shell" not in st for st in broken["runs"]["steps"] if "run" in st)
    assert "shell" in s["broken_actions"]["no_shell"]["github_error"]
    assert s["broken_actions"]["no_shell"]["actionlint_exit"] == 0

    wf = load_workflow(WORKFLOWS_DIR / "ch19-custom-actions.yml")
    assert set(wf["jobs"]) == {
        "composite", "remote_reference", "javascript", "javascript_post_after_failure",
        "docker_built", "docker_prebuilt"}
    if shutil.which("node"):
        res = subprocess.run(
            ["node", "--test", str(ACTIONS / "tally-js" / "test")],
            capture_output=True, text=True,
        )
        assert res.returncode == 0
    print("composite script, metadata rules, JS post step and Docker timings all asserted")


if __name__ == "__main__":
    main()
