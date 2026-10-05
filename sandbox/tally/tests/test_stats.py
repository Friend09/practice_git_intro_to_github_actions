"""Tests for tally.stats."""

import pytest

from tally.stats import clamp, mean, median


def test_mean() -> None:
    """The mean of 1, 2, 3 is 2."""
    assert mean([1, 2, 3]) == 2


def test_mean_empty() -> None:
    """An empty list is an error."""
    with pytest.raises(ValueError):
        mean([])


def test_median_odd_and_even() -> None:
    """Odd length picks the middle; even length averages the two middles."""
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5


def test_median_empty() -> None:
    """An empty list is an error."""
    with pytest.raises(ValueError):
        median([])


def test_clamp() -> None:
    """Values are limited to the interval."""
    assert clamp(5, 0, 3) == 3
    assert clamp(-1, 0, 3) == 0
    assert clamp(2, 0, 3) == 2
