"""Lab 23: the capstone pipeline, reviewed statically and checked against real runs.

Run: ``uv run python labs/lab_23_capstone.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.cost import mills_to_dollars, run_cost_mills, run_minutes
from intro_gha.injection import injection_sites
from intro_gha.pinning import unpinned
from intro_gha.workflow import execution_waves, job_graph, load_workflow


def review(workflow: dict) -> list[str]:
    """Return findings from the capstone review checklist (empty means clean)."""
    findings: list[str] = []
    if "permissions" not in workflow:
        findings.append("no top-level permissions")
    for job_id, job in workflow["jobs"].items():
        if "timeout-minutes" not in job:
            findings.append(f"{job_id}: no timeout-minutes")
    findings += [f"unpinned: {ref}" for ref in unpinned(workflow)]
    findings += [f"injection: {site}" for site in injection_sites(workflow)]
    return findings


def main() -> None:
    """Assert every claim made in Chapter 23."""
    s = json.loads((FIXTURES_DIR / "capstone_ch23_summary.json").read_text())
    wf = load_workflow(WORKFLOWS_DIR / "ch23-pipeline.yml")

    # Shape: waves from needs (Section 4).
    waves = execution_waves(job_graph(wf))
    assert waves == [
        ["lint", "test"], ["build"], ["verify"], ["deploy_staging"],
        ["deploy_production"], ["summary"],
    ]
    assert len(wf["jobs"]) == 7                                      # 7 job ids, 9 job runs
    assert len(wf["jobs"]["test"]["strategy"]["matrix"]["python"]) == 3

    # Review checklist is clean (Section 10) and catches a bad copy.
    assert review(wf) == []
    bad = json.loads(json.dumps(wf))
    del bad["permissions"]
    del bad["jobs"]["lint"]["timeout-minutes"]
    assert review(bad) == ["no top-level permissions", "lint: no timeout-minutes"]

    # Least privilege: only build can mint tokens (Chapter 15/16).
    writers = [j for j, spec in wf["jobs"].items() if "id-token" in spec.get("permissions", {})]
    assert writers == ["build"]
    assert wf["jobs"]["verify"]["permissions"]["attestations"] == "read"
    assert wf["jobs"]["deploy_production"]["if"].count("GHA_ENABLE_PROD") == 1

    # Green run (Section 6).
    g = s["green"]
    assert g["conclusion"] == "success" and g["skipped"] == ["deploy_production"]
    assert g["verify"] == {"verify": "", "digest_match": "yes", "attestation": "verified"}
    assert g["digest"].startswith("sha256:") and len(g["digest"]) == 7 + 64
    assert g["summary"]["production"] == "skipped" and g["summary"]["staging"] == "success"

    # Red run (Section 16): one failed leg stops everything after it, summary still runs.
    r = s["red"]
    assert r["failed"] == ["test (3.13)"]
    assert r["skipped"] == ["build", "verify", "deploy_staging", "deploy_production"]
    assert r["summary"]["test"] == "failure" and r["summary"]["build"] == "skipped"

    # Cost (Section 12): per-job round-up on the measured durations.
    green = [(sec, "linux") for sec in g["job_seconds"].values()]
    red = [(sec, "linux") for sec in r["job_seconds"].values()]
    assert (run_minutes(green), run_cost_mills(green)) == (8, 48)
    assert (run_minutes(red), run_cost_mills(red)) == (5, 30)
    assert mills_to_dollars(run_cost_mills(green)) == "$0.048"
    assert sum(g["job_seconds"].values()) == 121                     # one job: 3 minutes
    assert run_minutes([(121, "linux")]) == 3
    print("capstone shape, review checklist, least privilege, runs and cost all asserted")


if __name__ == "__main__":
    main()
