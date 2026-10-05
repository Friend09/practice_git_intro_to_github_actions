"""Tests for tally.stats (median is deliberately left untested)."""

from tally.stats import clamp, mean


def test_mean() -> None:
    """The mean of 1, 2, 3 is 2."""
    assert mean([1, 2, 3]) == 2


def test_clamp() -> None:
    """Values are limited to the interval."""
    assert clamp(5, 0, 3) == 3
    assert clamp(-1, 0, 3) == 0
    assert clamp(2, 0, 3) == 2
