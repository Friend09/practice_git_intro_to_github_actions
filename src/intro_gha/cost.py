"""Billing arithmetic for hosted runners.

Each job is billed per whole minute, rounded up, times the runner multiplier
(Linux 1x, Windows 2x, macOS 10x for standard runners).
"""

from __future__ import annotations

import math

MULTIPLIERS = {"linux": 1, "windows": 2, "macos": 10}


def billed_minutes(seconds: float, os_name: str = "linux") -> int:
    """Billed minutes for one job: ceil(seconds/60) times the OS multiplier."""
    return math.ceil(seconds / 60) * MULTIPLIERS[os_name]


def run_cost(jobs: list[tuple[float, str]]) -> int:
    """Total billed minutes for ``(seconds, os)`` jobs in a single workflow run."""
    return sum(billed_minutes(s, o) for s, o in jobs)
