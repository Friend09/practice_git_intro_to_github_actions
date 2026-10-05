"""Check the events model against real outcomes observed in this repository."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from intro_gha import FIXTURES_DIR, WORKFLOWS_DIR
from intro_gha.events import next_cron_run, would_fire
from intro_gha.workflow import load_workflow

OBS = json.loads((FIXTURES_DIR / "events_ch06_observed.json").read_text())
WFS = {n: load_workflow(WORKFLOWS_DIR / n) for n in OBS["workflows"]}


@pytest.mark.parametrize("obs", OBS["observations"], ids=lambda o: o["id"])
def test_model_matches_observed_runs(obs: dict) -> None:
    """The model predicts exactly the workflows that really fired."""
    present = obs.get("workflows", OBS["workflows"])
    predicted = sorted(
        n for n in present if would_fire(WFS[n], obs["event"])
    )
    assert predicted == sorted(obs["fired"])


def test_cron_yearly() -> None:
    """The demo cron fires once a year, Jan 1 at 04:23 UTC."""
    nxt = next_cron_run("23 4 1 1 *", datetime(2026, 10, 5, 12, 0))
    assert nxt == datetime(2027, 1, 1, 4, 23)


def test_cron_step_and_weekday() -> None:
    """Every 15 minutes, and Monday 09:00."""
    assert next_cron_run("*/15 * * * *", datetime(2026, 10, 5, 12, 1)) == datetime(
        2026, 10, 5, 12, 15
    )
    assert next_cron_run("0 9 * * 1", datetime(2026, 10, 5, 12, 0)) == datetime(
        2026, 10, 12, 9, 0
    )  # 2026-10-05 is a Monday; next one is a week later
