"""Tests for tally.add."""

from tally.add import add


def test_add_small_numbers() -> None:
    """2 + 3 is 5."""
    assert add(2, 3) == 5


def test_add_negative() -> None:
    """Adding a negative number subtracts."""
    assert add(2, -3) == -1
