"""Lab 09: outputs, artifacts, cache and the output-size limit, from real runs.

Run: ``uv run python labs/lab_09_data_outputs_artifacts_caching.py`` (offline).
"""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR
from intro_gha.cost import billed_minutes

LIMIT_BYTES = 1_048_576


def load(name: str) -> dict:
    """Load a JSON fixture by file name."""
    return json.loads((FIXTURES_DIR / name).read_text())


def output_fits(chars: int, bytes_per_char: int = 2) -> bool:
    """Would a job output of ``chars`` ASCII characters fit under the 1 MiB limit?"""
    return chars * bytes_per_char <= LIMIT_BYTES


def main() -> None:
    """Assert every number quoted in Chapter 09."""
    miss, hit, new = (load(f"data_ch09_{n}.json") for n in ("miss", "hit", "newkey"))
    assert [r["reports"]["consume"]["version"] for r in (miss, hit, new)] == [
        "0.1.1", "0.1.2", "0.1.3"]
    for r in (miss, hit, new):
        c = r["reports"]["consume"]
        assert c["digest_match"] == "yes" and c["no_checkout_here"] == "absent"
        assert c["notes_lines"] == "2" and c["notes_first"] == "line one"
        assert r["reports"]["build"]["strict_outcome"] == "failure"
        assert r["reports"]["build"]["duplicate_outcome"] == "failure"

    assert miss["reports"]["cache"]["cache_hit"] == "[]"      # empty on a miss
    assert hit["reports"]["cache"]["cache_hit"] == "[true]"
    assert miss["reports"]["cache"]["key"] != new["reports"]["cache"]["key"]
    assert miss["reports"]["cache"]["key"].endswith(hit["reports"]["cache"]["key"][-64:])

    def total(run: dict) -> int:
        """Sum of the cache job's step seconds."""
        return sum(s["seconds"] for s in run["cache_job_steps"])

    assert (total(miss), total(hit), total(new)) == (17, 4, 14)
    assert billed_minutes(total(miss)) == billed_minutes(total(hit)) == 1
    assert billed_minutes(95 + 20) == 2 and billed_minutes(6 + 20) == 1  # exercise 5

    art = load("artifacts_cache_ch09.json")["artifact"]
    assert art["size_in_bytes"] == 277 and art["raw_bytes"] == 2048
    assert art["expires_at"][:10] == "2026-10-06" and art["created_at"][:10] == "2026-10-05"
    events = load("artifacts_cache_ch09.json")["artifact_events"]
    assert events["empty_default"]["level"] == "warning"
    assert "409" in events["duplicate_name"]["message"]

    lim = load("output_limits_ch09.json")
    by = {p["job"]: p for p in lim["probes"]}
    assert by["p520k"]["result"] == "success" and by["p530k"]["result"] == "failure"
    assert 520_000 * 2 <= LIMIT_BYTES < 530_000 * 2
    assert output_fits(520_000) and not output_fits(530_000)
    assert billed_minutes(by["p400k"]["job_seconds"]) == 3
    assert billed_minutes(by["p520k"]["job_seconds"]) == 4
    for name in ("p400k", "p520k", "p530k"):  # quadratic fit within 2 seconds
        p = by[name]
        assert abs(p["job_seconds"] - p["quadratic_prediction_s"]) <= 2, name
    print("outputs, artifacts and cache match the real runs; limit ~524,288 chars")


if __name__ == "__main__":
    main()
