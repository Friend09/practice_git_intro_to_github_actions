"""Lab 14: SemVer rules, release facts and notes behavior, from real releases.

Run: ``uv run python labs/lab_14_release_automation.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.semver import latest, parse, tag_to_version
from intro_gha.workflow import load_workflow


def checksum_line_bytes(filename: str) -> int:
    """Size of one ``SHA256SUMS`` line: 64 hex, two spaces, ``./name``, newline."""
    return 64 + 2 + len("./" + filename) + 1


def main() -> None:
    """Assert every claim made in Chapter 14."""
    assert str(tag_to_version("v0.1.0")) == "0.1.0"
    for bad in ("1.0", "v1.0.0", "01.0.0", "1.0.0.0", ""):
        try:
            parse(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert latest(["0.1.9", "0.1.10"]) == "0.1.10"
    assert latest(["1.0.0-rc.1", "1.0.0"]) == "1.0.0"
    assert latest(["1.0.0-alpha.2", "1.0.0-alpha.10"]) == "1.0.0-alpha.10"
    order = sorted(["2.0.0", "2.0.0-beta.1", "1.9.10", "1.9.9"],
                   key=lambda v: parse(v).sort_key())
    assert order == ["1.9.9", "1.9.10", "2.0.0-beta.1", "2.0.0"]  # exercise 1
    assert str(parse("0.1.2").bump("patch")) == "0.1.3"

    s = json.loads((FIXTURES_DIR / "release_ch14_summary.json").read_text())
    tag = s["tag_push"]
    assert tag["created_by"] == "user credentials" and tag["conclusion"] == "success"
    assert set(tag["other_workflows_fired_on_the_tag"]) == {"ch03 tally ci", "ch11 python ci"}
    assert tag["jobs"]["publish_pypi_guarded"] == "skipped"
    assert tag["wheel_metadata"]["Version"] == "0.1.0" and tag["checksums_verified"]
    names = {a["name"]: a for a in tag["release"]["assets"]}
    assert set(names) == {"SHA256SUMS", "tally_demo-0.1.0-py3-none-any.whl", "tally_demo-0.1.0.tar.gz"}
    assert all(a["digest"].startswith("sha256:") and len(a["digest"]) == 71 for a in names.values())
    expected = (checksum_line_bytes("tally_demo-0.1.0-py3-none-any.whl")
                + checksum_line_bytes("tally_demo-0.1.0.tar.gz"))
    assert expected == names["SHA256SUMS"]["size"] == 194  # exercise 5

    n = s["notes"]["preview_for_v0.1.0"]
    assert n["categories"] == ["Features"] and not n["direct_commits_listed"]
    d = s["dispatch"]
    assert d["tag_created_by"] == "GITHUB_TOKEN" and d["push_runs_started_for_tag"] == 0
    assert d["auto_notes_repeated_pr_2"] and "empty" in d["notes_with_previous_tag_v0.1.0"]
    assert s["notes_start_tag"]["notes_start_tag"] == "v0.1.1"
    bad = s["invalid_version"]
    assert (bad["build"], bad["release"]) == ("failure", "skipped")
    assert bad["annotation_title"] == "Not a semantic version"
    assert all(not r["latest"] and r["prerelease"] for r in s["releases_listed"])

    im = s["immutable"]
    assert im["baseline"] == {"upload_asset": "ok", "delete_asset": "ok"}
    assert "Cannot upload assets" in im["upload_extra_asset"]
    assert "Cannot delete asset" in im["delete_asset"] and "Cannot delete this tag" in im["delete_tag"]
    assert im["after_disabling_setting"] == {"v0.1.3": True, "v0.1.2": False}

    wf = load_workflow(WORKFLOWS_DIR / "ch14-release.yml")
    assert wf["jobs"]["release"]["permissions"] == {"contents": "write"}
    assert wf["jobs"]["publish_pypi_guarded"]["if"] == "${{ vars.GHA_ENABLE_PYPI == 'true' }}"
    pin = wf["jobs"]["publish_pypi_guarded"]["steps"][-1]["uses"].split("@")[1].split()[0]
    assert len(pin) == 40
    print("SemVer, assets, notes behavior, token-tag rule and immutability all asserted")


if __name__ == "__main__":
    main()
