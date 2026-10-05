"""Lab 13: deployment records, branch rules and OIDC trust policy evaluation.

Run: ``uv run python labs/lab_13_continuous_deployment.py`` (offline; all asserted).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.oidc import immutable_sub, legacy_sub, sub_pattern_matches, trust_allows
from intro_gha.workflow import load_workflow

OWNER, OID, REPO, RID = "Friend09", 7501015, "practice_git_intro_to_github_actions", 1405684500


def token_expired(iat: int, lifetime: int, now: int) -> bool:
    """A token is expired once ``now`` reaches ``iat + lifetime``."""
    return now >= iat + lifetime


def main() -> None:
    """Assert every claim made in Chapter 13."""
    s = json.loads((FIXTURES_DIR / "deploy_ch13_summary.json").read_text())
    dep, oidc = s["deployments"], s["oidc"]
    assert dep["approved"]["statuses"][0] == "waiting"
    assert dep["approved"]["statuses"][-1] == "success"
    assert dep["branch_restriction"]["statuses"] == ["waiting", "failure"]
    assert "not allowed to deploy to production" in dep["branch_restriction"]["annotations"][0]
    assert dep["branch_restriction"]["policy"]["allowed"] == ["main"]
    assert dep["branch_restriction"]["job_conclusion"] == "failure"

    assert oidc["alg"] == "RS256" and oidc["lifetime_seconds"] == 300
    assert oidc["signature_valid"] and oidc["wrong_audience"] == "rejected"
    assert oidc["tampered_signature"] == "rejected" and len(oidc["claim_names"]) == 33
    assert oidc["no_id_token_permission"]["request_url"] == "absent"
    assert token_expired(1000, 300, 1400) and not token_expired(1000, 300, 1250)

    c = oidc["claims"]
    iss, aud = oidc["issuer"], "sts.amazonaws.com"
    tok = {k: {"iss": iss, "aud": aud, "sub": v["sub"]} for k, v in c.items()}
    assert c["with_environment_main"]["sub"] == c["with_environment_branch"]["sub"]
    assert c["without_environment_main"]["sub"] != c["without_environment_branch"]["sub"]
    assert c["with_environment_main"]["ref"] != c["with_environment_branch"]["ref"]
    assert c["with_environment_main"]["sub"] == immutable_sub(
        OWNER, OID, REPO, RID, "environment:staging")

    prod = {"iss": iss, "aud": aud, "sub": immutable_sub(
        OWNER, OID, REPO, RID, "environment:production")}
    assert trust_allows(tok["with_environment_main"], prod) == (False, "subject does not match")
    legacy = {"iss": iss, "aud": aud, "sub": legacy_sub(OWNER, REPO, "environment:staging")}
    assert not trust_allows(tok["with_environment_main"], legacy)[0]
    pin = {"iss": iss, "aud": aud, "sub": immutable_sub(OWNER, OID, REPO, RID, "ref:refs/heads/main")}
    assert trust_allows(tok["without_environment_main"], pin)[0]
    assert not trust_allows(tok["without_environment_branch"], pin)[0]
    wide = immutable_sub(OWNER, OID, REPO, RID, "*")
    assert sub_pattern_matches(wide, tok["with_environment_branch"]["sub"])
    assert trust_allows({**tok["with_environment_main"], "aud": "x"}, prod)[1] == "audience mismatch"

    wf = load_workflow(WORKFLOWS_DIR / "ch13-deploy.yml")
    jobs = wf["jobs"]
    assert jobs["oidc_with_environment"]["permissions"]["id-token"] == "write"
    assert "id-token" not in jobs["oidc_without_permission"]["permissions"]
    assert jobs["deploy_cloud_guarded"]["if"] == "${{ vars.GHA_ENABLE_AWS_OIDC == 'true' }}"
    uses = jobs["deploy_cloud_guarded"]["steps"][0]["uses"]
    assert uses.split("@")[1].startswith("e1253824e5c1") and len(uses.split("@")[1].split()[0]) == 40
    print("deployments, branch rule, token facts and trust policy cases all asserted")


if __name__ == "__main__":
    main()
