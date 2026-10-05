"""Tests for the SemVer helpers."""

import pytest

from intro_gha.semver import latest, parse, tag_to_version


def test_parse_and_render() -> None:
    """Parsing then rendering round-trips."""
    assert str(parse("0.1.0")) == "0.1.0"
    assert str(parse("1.2.3-rc.1")) == "1.2.3-rc.1"


@pytest.mark.parametrize("bad", ["1.0", "v1.0.0", "01.0.0", "1.0.0.0", "1.0.0-", ""])
def test_rejects_non_semver(bad: str) -> None:
    """Two-part, leading-v, leading-zero and empty strings are rejected."""
    with pytest.raises(ValueError):
        parse(bad)


def test_bump() -> None:
    """Bumping resets the lower parts."""
    assert str(parse("0.1.9").bump("minor")) == "0.2.0"
    assert str(parse("1.4.2").bump("major")) == "2.0.0"
    assert str(parse("1.4.2-rc.1").bump("patch")) == "1.4.3"


def test_ordering_puts_prereleases_below_release() -> None:
    """1.0.0-rc.1 < 1.0.0, and 0.1.10 > 0.1.9 (numeric, not text, comparison)."""
    assert latest(["1.0.0-rc.1", "1.0.0"]) == "1.0.0"
    assert latest(["0.1.9", "0.1.10"]) == "0.1.10"
    assert latest(["1.0.0-alpha.2", "1.0.0-alpha.10"]) == "1.0.0-alpha.10"


def test_tag_requires_v() -> None:
    """Release tags carry a leading v."""
    assert str(tag_to_version("v2.0.1")) == "2.0.1"
    with pytest.raises(ValueError):
        tag_to_version("2.0.1")
