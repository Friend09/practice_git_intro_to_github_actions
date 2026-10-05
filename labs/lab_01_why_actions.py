"""Lab 01: Tally's CI bill, the rounding penalty, and the monthly overage.

Run: ``uv run python labs/lab_01_why_actions.py`` (offline; every figure is asserted).
"""

from __future__ import annotations

from intro_gha.cost import (
    FREE_MINUTES,
    job_cost_mills,
    mills_to_dollars,
    run_cost_mills,
    run_minutes,
)

SPLIT = [(15, "linux"), (20, "linux"), (25, "linux")]
MERGED = [(60, "linux")]


def monthly_overage_mills(jobs: list[tuple[float, str]], pushes: int, plan: str) -> int:
    """Overage in mills for ``pushes`` runs of ``jobs`` on a private repo ``plan``.

    Overage minutes are priced at the Linux rate (all jobs here are Linux).
    """
    over = max(0, pushes * run_minutes(jobs) - FREE_MINUTES[plan])
    return over * job_cost_mills(60, "linux")


def main() -> None:
    """Print and assert every figure in Chapter 01."""
    assert run_minutes(SPLIT) == 3 and run_minutes(MERGED) == 1
    assert run_cost_mills(SPLIT) == 18 and run_cost_mills(MERGED) == 6
    print("split:", mills_to_dollars(run_cost_mills(SPLIT)), "merged:",
          mills_to_dollars(run_cost_mills(MERGED)))
    assert monthly_overage_mills(SPLIT, 200, "free") == 0
    assert monthly_overage_mills(SPLIT, 1000, "free") == 6000
    assert monthly_overage_mills(MERGED, 1000, "free") == 0
    print("1000 pushes, split:", mills_to_dollars(monthly_overage_mills(SPLIT, 1000, "free")))
    assert job_cost_mills(61, "macos") == 124
    assert job_cost_mills(61, "linux") == 12
    assert run_cost_mills([(45, "linux"), (45, "windows"), (45, "macos")]) == 78
    print("exercise 5 matrix run:", mills_to_dollars(78))


if __name__ == "__main__":
    main()
