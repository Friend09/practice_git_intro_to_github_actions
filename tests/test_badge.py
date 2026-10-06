"""Tests for ``intro_gha.badge`` against badge titles seen on the live repository."""

from __future__ import annotations

import json

from intro_gha import FIXTURES_DIR
from intro_gha.badge import badge_markdown, badge_status, badge_url

FIX = json.loads((FIXTURES_DIR / "badge_ch03.json").read_text())


def test_badge_url_matches_observed_queries() -> None:
    """Every observed query string is what ``badge_url`` builds."""
    for item in FIX["badges"]:
        query = item["query"].lstrip("?")
        params = dict(p.split("=") for p in query.split("&")) if query else {}
        url = badge_url(FIX["repo"], FIX["workflow_file"], **params)
        assert url.endswith("badge.svg" + item["query"])


def test_badge_status_reads_the_title() -> None:
    """The status word is the text after the last ' - ' in the SVG title."""
    statuses = [
        badge_status(f"<svg><title>{b['title']}</title></svg>") for b in FIX["badges"]
    ]
    assert statuses == ["passing", "passing", "passing", "failing", "no status"]


def test_badge_markdown_links_to_run_list() -> None:
    """The Markdown image is wrapped in a link to the workflow's run list."""
    md = badge_markdown(FIX["repo"], FIX["workflow_file"], "ch03", branch="main")
    assert md.startswith("[![ch03](https://github.com/") and md.endswith(
        "/actions/workflows/ch03-tally-ci.yml)"
    )
    assert "?branch=main" in md
