"""Capture ``REPORT key=value`` lines from a real run's logs into a fixture.

Usage: ``uv run python scripts/capture_reports.py RUN_ID fixtures/name.json``.
Each job's lines are stored under its name; the run's metadata is included so the
fixture documents exactly which real run it came from.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

LINE = re.compile(r"^(?P<job>[^\t]+)\t[^\t]*\t﻿?\S+Z (?P<text>.*)$")
REPORT = re.compile(r"^REPORT (?P<body>.+)$")


def gh(*args: str) -> str:
    """Run a ``gh`` command and return stdout (raises on failure)."""
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def capture(run_id: str) -> dict:
    """Return ``{run metadata, reports: {job: {key: value}}}`` for a run."""
    meta = json.loads(gh("run", "view", run_id, "--json",
                         "event,conclusion,headSha,displayTitle"))
    reports: dict[str, dict[str, str]] = {}
    for raw in gh("run", "view", run_id, "--log").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        r = REPORT.match(m["text"].strip())
        if not r or r["body"].startswith("echo"):
            continue
        for pair in re.split(r"\s(?=\w+=)", r["body"]):
            key, _, value = pair.partition("=")
            reports.setdefault(m["job"], {})[key] = value
    return {"run_id": int(run_id), **meta, "reports": reports}


def main() -> None:
    """CLI entry point."""
    run_id, out = sys.argv[1], Path(sys.argv[2])
    out.write_text(json.dumps(capture(run_id), indent=2) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    main()
