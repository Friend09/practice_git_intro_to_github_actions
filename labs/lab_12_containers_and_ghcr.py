"""Lab 12: image reference rules and the real container run's results.

Run: ``uv run python labs/lab_12_containers_and_ghcr.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.cost import billed_minutes
from intro_gha.images import ghcr_ref, repository_name_ok
from intro_gha.workflow import load_workflow


def main() -> None:
    """Assert every claim made in Chapter 12."""
    s = json.loads((FIXTURES_DIR / "containers_ch12_summary.json").read_text())
    run = json.loads((FIXTURES_DIR / "containers_ch12_run.json").read_text())["reports"]

    digest = s["publish"]["digest"]
    assert digest.startswith("sha256:") and len(digest) == 7 + 64
    assert run["publish"]["digest"] == run["verify"]["digest"] == digest
    assert run["verify"]["verify_output"] == "5" and s["verify"]["digest_equal"]

    assert not repository_name_ok("ghcr.io/Friend09/tally:test")
    assert "repository name must be lowercase" in s["uppercase"]["error"]
    assert run["uppercase_tag"]["uppercase_build_outcome"] == "failure"
    assert run["uppercase_tag"]["owner"] == "Friend09"
    ref = ghcr_ref("Friend09", "tally", tag="latest")
    assert ref == "ghcr.io/friend09/tally:latest" and repository_name_ok(ref)
    assert ghcr_ref("Friend09", "tally", digest=digest).endswith("@" + digest)
    for bad in ("sha256:abc", "md5:" + "a" * 64):
        try:
            ghcr_ref("o", "n", digest=bad)
        except ValueError:
            continue
        raise AssertionError(bad)

    assert run["publish_denied"]["denied_push_outcome"] == "failure"
    assert s["denied"]["error"].startswith("denied:") and not s["denied"]["package_created"]
    assert run["service"]["redis_reply"] == "+PONG"
    assert s["service"]["health_progression"] == ["starting", "healthy"]
    ic = run["in_container"]
    assert ic["git"] == "none" and ic["has_pyproject"] == "yes"
    assert ic["container_os"].startswith("Debian") and ic["files_after_checkout"] == "20"

    mib = s["publish"]["compressed_bytes"] / 1_048_576
    assert round(mib, 2) == 45.05 and s["publish"]["layers"] == 6
    assert 20 * s["publish"]["compressed_bytes"] == 944_720_760
    assert billed_minutes(s["publish"]["job_seconds"]) == 1

    wf = load_workflow(WORKFLOWS_DIR / "ch12-containers.yml")
    assert wf["jobs"]["publish"]["permissions"]["packages"] == "write"
    assert wf["jobs"]["publish_denied"]["permissions"] == {"contents": "read"}
    assert wf["jobs"]["verify"]["needs"] == ["publish"]
    print("image refs, lowercase rule, digest verification and permissions all asserted")


if __name__ == "__main__":
    main()
