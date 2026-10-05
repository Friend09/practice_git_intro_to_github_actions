"""A tiny model of how a cloud provider evaluates a GitHub OIDC trust policy.

Real clouds (AWS IAM, GCP workload identity, Azure) check the token's signature, then
compare claims such as ``iss``, ``aud`` and ``sub`` against conditions you configured.
This module reproduces only that comparison step so Chapter 13 can test policies
against the real claims captured from this repository's runs. It is a teaching model,
not a substitute for the provider's own evaluation.
"""

from __future__ import annotations

import re
from typing import Any


def sub_pattern_matches(pattern: str, sub: str) -> bool:
    """Match a ``sub`` condition where ``*`` is a wildcard (like IAM ``StringLike``)."""
    regex = "^" + ".*".join(re.escape(part) for part in pattern.split("*")) + "$"
    return re.match(regex, sub) is not None


def trust_allows(claims: dict[str, Any], policy: dict[str, Any]) -> tuple[bool, str]:
    """Return ``(allowed, reason)`` for ``claims`` under ``policy``.

    ``policy`` keys: ``iss`` (exact), ``aud`` (exact) and ``sub`` (a pattern or list of
    patterns with ``*`` wildcards). Every key must match.
    """
    if claims.get("iss") != policy["iss"]:
        return False, "issuer mismatch"
    if claims.get("aud") != policy["aud"]:
        return False, "audience mismatch"
    subs = policy["sub"] if isinstance(policy["sub"], list) else [policy["sub"]]
    if not any(sub_pattern_matches(p, claims["sub"]) for p in subs):
        return False, "subject does not match"
    return True, "allowed"


def immutable_sub(owner: str, owner_id: int, repo: str, repo_id: int, tail: str) -> str:
    """Build the immutable-format ``sub``: ``repo:OWNER@ID/REPO@ID:<tail>``.

    ``tail`` is ``environment:NAME`` or ``ref:refs/heads/BRANCH`` and so on.
    """
    return f"repo:{owner}@{owner_id}/{repo}@{repo_id}:{tail}"


def legacy_sub(owner: str, repo: str, tail: str) -> str:
    """Build the older ``sub`` format ``repo:OWNER/REPO:<tail>`` (no numeric IDs)."""
    return f"repo:{owner}/{repo}:{tail}"
