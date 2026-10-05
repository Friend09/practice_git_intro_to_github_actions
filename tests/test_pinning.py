"""Tests for the pin classifier."""

from intro_gha.pinning import classify, unpinned

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


def test_classify_forms() -> None:
    """Each reference form is recognized."""
    assert classify("./.github/actions/x") == "local"
    assert classify("docker://alpine:3.20") == "docker"
    assert classify(f"actions/checkout@{SHA}") == "sha"
    assert classify("actions/checkout@v7") == "tag-or-branch"
    assert classify("actions/checkout@main") == "tag-or-branch"
    assert classify("actions/checkout@" + SHA[:7]) == "tag-or-branch"  # short SHAs move


def test_unpinned_lists_only_movable_refs() -> None:
    """Local, docker and full-SHA references are not flagged."""
    wf = {"jobs": {"a": {"steps": [
        {"uses": "actions/checkout@v7"}, {"uses": f"actions/cache@{SHA}"},
        {"uses": "./local"}, {"uses": "docker://alpine:3.20"}]}}}
    assert unpinned(wf) == ["actions/checkout@v7"]
