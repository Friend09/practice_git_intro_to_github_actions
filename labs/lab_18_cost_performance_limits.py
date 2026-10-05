"""Lab 18: price this repo's job history, the merge what-if, queue latency, caches.

Run: ``uv run python labs/lab_18_cost_performance_limits.py`` (offline; all asserted).
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime

from intro_gha import FIXTURES_DIR
from intro_gha.cost import RATE_MILLS_PER_MIN, billed_minutes, mills_to_dollars

FMT = "%Y-%m-%dT%H:%M:%SZ"


def os_of(label: str) -> str:
    """Map a runner label to the billing OS."""
    if label.startswith("macos"):
        return "macos"
    return "windows" if label.startswith("windows") else "linux"


def jobs_that_ran() -> list[dict]:
    """Jobs that were assigned a runner, with seconds, OS and queue latency."""
    snap = json.loads((FIXTURES_DIR / "jobs_ch18_snapshot.json").read_text())
    ran = []
    for j in snap["jobs"]:
        if j["conclusion"] == "skipped" or j["labels"][0] == "self-hosted":
            continue
        s, e, c = (datetime.strptime(j[k], FMT)
                   for k in ("started_at", "completed_at", "created_at"))
        if e < s:
            continue
        ran.append({**j, "sec": int((e - s).total_seconds()),
                    "os": os_of(j["labels"][0]), "queue_s": int((s - c).total_seconds())})
    return ran


def cost_mills(jobs: list[dict]) -> int:
    """Per-job billed cost in mills."""
    return sum(billed_minutes(j["sec"]) * RATE_MILLS_PER_MIN[j["os"]] for j in jobs)


def merged_cost_mills(jobs: list[dict]) -> int:
    """Cost if each run's same-OS jobs were merged into one job."""
    groups: dict[tuple, int] = defaultdict(int)
    for j in jobs:
        groups[(j["run_id"], j["os"])] += j["sec"]
    return sum(billed_minutes(s) * RATE_MILLS_PER_MIN[o] for (_, o), s in groups.items())


def main() -> None:
    """Assert every number quoted in Chapter 18."""
    ran = jobs_that_ran()
    assert len(ran) == 337
    used = sum(j["sec"] for j in ran)
    billed = sum(billed_minutes(j["sec"]) for j in ran)
    assert (used, billed) == (6357, 390) and round(billed * 60 / used, 2) == 3.68
    assert cost_mills(ran) == 2400 and mills_to_dollars(2400) == "$2.400"
    assert round(100 * billed / 2000, 1) == 19.5
    assert sum(j["sec"] <= 30 for j in ran) == 316 and sum(j["sec"] <= 60 for j in ran) == 324
    merged = merged_cost_mills(ran)
    assert merged == 1500 and round(100 * (2400 - merged) / 2400) == 38

    qs = sorted(j["queue_s"] for j in ran if j["queue_s"] >= 0)
    assert statistics.median(qs) == 3 and qs[int(0.9 * len(qs))] == 4 and qs[-1] == 72

    probe = [j for j in ran if j["workflow"] == "ch09-output-limits.yml"]
    assert len(probe) == 4 and sum(billed_minutes(j["sec"]) for j in probe) == 39
    mac = [j for j in ran if j["os"] == "macos"]
    assert len(mac) == 1 and cost_mills(mac) == 62 and round(100 * 62 / 2400, 1) == 2.6

    cb = json.loads((FIXTURES_DIR / "cache_benefit_ch18.json").read_text())
    pip = {r["label"]: r for r in cb["runs"]}
    assert [int(pip[k]["report"]["install_seconds"]) for k in
            ("no cache", "cache miss (first)", "cache hit")] == [49, 44, 43]
    assert pip["no cache"]["report"]["site_packages_mb"] == "1329"
    uv = {r["label"]: r for r in cb["uv_runs"]}
    assert [r["job_seconds"] for r in (uv["uv, cache off"], uv["uv, cache miss"],
                                       uv["uv, cache hit"])] == [9, 16, 13]
    assert uv["uv, cache off"]["job_seconds"] < uv["uv, cache hit"]["job_seconds"]
    assert all(billed_minutes(r["job_seconds"]) == 1
               for r in list(pip.values()) + list(uv.values()))

    assert billed_minutes(25) == 1 and billed_minutes(75) == 2        # exercise 1
    assert 200 * 4 == 800 and 200 * billed_minutes(80) == 400          # exercise 2
    assert 5 + 1 > 3                                                  # exercise 3
    assert 24 * 30 * billed_minutes(40) == 720                        # exercise 4
    assert 12 * 24 * 30 == 8640 and round(8640 * 6 / 1000, 2) == 51.84
    assert round((8640 - 3000) * 6 / 1000, 2) == 33.84
    print("bill model, merge what-if, queue latency and cache experiments all asserted")


if __name__ == "__main__":
    main()
