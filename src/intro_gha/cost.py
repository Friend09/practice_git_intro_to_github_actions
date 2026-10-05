"""Billing arithmetic for GitHub-hosted runners.

Rates are GitHub's per-minute overage prices for standard runners (verified against
GitHub Docs 2026-10), stored as integer *mills* (1 mill = $0.001) to avoid float error:
Linux 2-core $0.006, Windows 2-core $0.010, macOS $0.062. Each job's time is rounded
up to a whole minute. Standard runners are free on public repos; private repos get a
monthly allowance (Free plan: 2,000 minutes) before overage applies.
"""

from __future__ import annotations

import math

RATE_MILLS_PER_MIN = {"linux": 6, "windows": 10, "macos": 62}
FREE_MINUTES = {"free": 2000, "pro": 3000, "team": 3000, "enterprise": 50000}


def billed_minutes(seconds: float) -> int:
    """Whole billed minutes for one job: ``ceil(seconds / 60)``, minimum 1."""
    return max(1, math.ceil(seconds / 60))


def job_cost_mills(seconds: float, os_name: str = "linux") -> int:
    """Overage cost of one job in mills: billed minutes times the OS rate."""
    return billed_minutes(seconds) * RATE_MILLS_PER_MIN[os_name]


def run_cost_mills(jobs: list[tuple[float, str]]) -> int:
    """Total overage cost in mills for ``(seconds, os)`` jobs in one workflow run."""
    return sum(job_cost_mills(s, o) for s, o in jobs)


def run_minutes(jobs: list[tuple[float, str]]) -> int:
    """Total billed minutes across the jobs of one run (all OSes)."""
    return sum(billed_minutes(s) for s, _ in jobs)


def mills_to_dollars(mills: int) -> str:
    """Format mills as a dollar string, e.g. ``124 -> '$0.124'``."""
    return f"${mills / 1000:.3f}"
