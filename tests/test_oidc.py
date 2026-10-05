"""The OIDC trust model, tested against claims captured from real runs."""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR
from intro_gha.oidc import immutable_sub, legacy_sub, sub_pattern_matches, trust_allows

D = json.loads((FIXTURES_DIR / "deploy_ch13_summary.json").read_text())["oidc"]
ISS, AUD = D["issuer"], "sts.amazonaws.com"
OWNER, OID, REPO, RID = "Friend09", 7501015, "practice_git_intro_to_github_actions", 1405684500


def claims(key: str) -> dict:
    """Real claims (iss, aud, sub) captured for one run variant."""
    return {"iss": ISS, "aud": AUD, "sub": D["claims"][key]["sub"]}


def test_real_sub_has_the_immutable_format() -> None:
    """Our repo (created after 2026-07-15) gets owner and repo IDs in the sub."""
    sub = D["claims"]["with_environment_main"]["sub"]
    assert sub == immutable_sub(OWNER, OID, REPO, RID, "environment:staging")
    assert sub != legacy_sub(OWNER, REPO, "environment:staging")


def test_environment_policy_allows_only_that_environment() -> None:
    """A policy on environment:production rejects the staging token."""
    policy = {"iss": ISS, "aud": AUD,
              "sub": immutable_sub(OWNER, OID, REPO, RID, "environment:production")}
    assert trust_allows(claims("with_environment_main"), policy) == (
        False, "subject does not match")


def test_legacy_format_policy_silently_fails() -> None:
    """A policy copied from an older tutorial never matches the new sub."""
    policy = {"iss": ISS, "aud": AUD, "sub": legacy_sub(OWNER, REPO, "environment:staging")}
    assert not trust_allows(claims("with_environment_main"), policy)[0]


def test_environment_sub_ignores_the_branch() -> None:
    """The environment sub is identical on main and a feature branch."""
    assert claims("with_environment_main")["sub"] == claims("with_environment_branch")["sub"]
    assert claims("without_environment_main")["sub"] != claims("without_environment_branch")["sub"]


def test_ref_policy_pins_the_branch() -> None:
    """A ref-based sub pattern allows main and rejects the feature branch."""
    policy = {"iss": ISS, "aud": AUD,
              "sub": immutable_sub(OWNER, OID, REPO, RID, "ref:refs/heads/main")}
    assert trust_allows(claims("without_environment_main"), policy)[0]
    assert not trust_allows(claims("without_environment_branch"), policy)[0]


def test_wildcards_widen_trust() -> None:
    """A trailing wildcard accepts every ref and environment of the repo."""
    prefix = immutable_sub(OWNER, OID, REPO, RID, "")
    assert sub_pattern_matches(prefix + "*", claims("with_environment_branch")["sub"])
    assert not sub_pattern_matches(prefix + "environment:production", claims(
        "with_environment_main")["sub"])


def test_audience_and_issuer_must_match() -> None:
    """Wrong audience or issuer is rejected before the subject is looked at."""
    good = claims("with_environment_main")
    sub = good["sub"]
    assert trust_allows({**good, "aud": "sts.wrong"}, {"iss": ISS, "aud": AUD, "sub": sub})[1] == "audience mismatch"
    assert trust_allows({**good, "iss": "https://evil.example"}, {"iss": ISS, "aud": AUD, "sub": sub})[1] == "issuer mismatch"
