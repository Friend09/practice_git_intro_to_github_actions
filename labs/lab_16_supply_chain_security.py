"""Lab 16: pin classification, injection, PR triggers, policies and attestations.

Run: ``uv run python labs/lab_16_supply_chain_security.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.injection import injection_sites, interpolate, untrusted_expressions
from intro_gha.pinning import classify, unpinned
from intro_gha.workflow import load_workflow

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


def main() -> None:
    """Assert every claim made in Chapter 16."""
    s = json.loads((FIXTURES_DIR / "security_ch16_summary.json").read_text())

    assert classify(f"actions/checkout@{SHA}") == "sha"
    assert classify("actions/checkout@v7") == "tag-or-branch"
    assert classify("actions/checkout@" + SHA[:7]) == "tag-or-branch"
    exempt = set(s["pinning"]["exempt_workflows"])
    loose = {
        p.name: unpinned(load_workflow(p))
        for p in WORKFLOWS_DIR.glob("*.yml") if p.name not in exempt
    }
    assert all(not v for v in loose.values()), loose
    assert s["pinning"]["references_pinned_by_script"] == 29

    tv = s["pinning"]["tag_object_vs_commit"]
    assert tv["ref_object_type"] == "tag" and tv["tag_object_sha"] != tv["commit_sha"]
    assert tv["tag_object_downloaded_at_setup"] and tv["commit_downloaded_at_setup"]
    prop = s["pinning"]["dependabot"]["proposed"]
    assert (prop["from"], prop["to"]) == (tv["tag_object_sha"], tv["commit_sha"])
    assert tv["commit_sha"] in (WORKFLOWS_DIR / "ch14-release.yml").read_text()
    assert tv["tag_object_sha"] not in (WORKFLOWS_DIR / "ch14-release.yml").read_text()

    inj = s["injection"]
    script = 'echo "REPORT vulnerable_title=${{ inputs.title }}"'
    assert interpolate(script, {"inputs.title": inj["payload"]}) == inj["vulnerable"]["command_line_run"]
    assert inj["vulnerable"]["injected_user"] == "runner"
    assert inj["safe"]["payload_printed_literally"]
    assert untrusted_expressions('echo "$TITLE"') == []
    sites = injection_sites(load_workflow(WORKFLOWS_DIR / "ch16-injection.yml"))
    assert [x[0] for x in sites] == ["vulnerable"]

    pr = s["pr_context"]
    assert pr["pull_request"]["workflow_version"] == "head-version"
    assert pr["pull_request_target"]["workflow_version"] == "base-version"
    assert pr["pull_request"]["github_sha"] == pr["pr_merge_commit_sha"][:7]
    assert pr["pull_request_target"]["github_sha"] == pr["pr_base_sha"][:7]
    assert pr["pull_request"]["head_sha"] == pr["pull_request_target"]["head_sha"]
    assert pr["pull_request_target"]["head_marker_under_target"] == "head-content"
    assert pr["pull_request_target"]["marker"] == "base-content"

    pol = s["sha_policy"]
    assert pol["on"]["unpinned_tag"].startswith("failure at Set up job")
    assert pol["off"]["unpinned_tag"] == pol["on"]["pinned"] == "success"
    assert "full-length commit SHA" in pol["message"]
    al = s["allow_list"]["restricted"]
    assert (al["conclusion"], al["jobs"]) == ("startup_failure", 0)
    assert not al["github_owned_job_ran"] and not al["api_message_available"]

    at = s["attestation"]
    assert at["predicate"] == "https://slsa.dev/provenance/v1"
    assert at["verify_in_workflow"] == "ok" and at["tampered"].startswith("rejected")
    assert at["wheel_digest"] != at["tampered_digest"]
    assert at["signer"].endswith("ch16-attest.yml@refs/heads/main")
    rs = json.loads((FIXTURES_DIR / "rulesets_ch16.json").read_text())
    prs = rs["prs"]
    assert prs["9"]["mergeable_state"] == "clean"
    assert prs["10"]["ci_ok"] == ["failure", "failure"]
    assert prs["11"]["ci_ok"] == [] and prs["11"]["mergeable_state"] == "blocked"
    assert rs["rename_variant"]["pr9_mergeable_state"] == "blocked"
    assert set(rs["tag_ruleset"]["rules"]) == {"deletion", "update"}
    codeowners = (WORKFLOWS_DIR.parent / "CODEOWNERS").read_text()
    assert "/.github/workflows/" in codeowners
    print("pins, injection, PR triggers, both policies and attestation all asserted")


if __name__ == "__main__":
    main()
