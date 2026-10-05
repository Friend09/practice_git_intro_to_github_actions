"""Unit tests for the intro_gha helpers (the hand-computed numbers in the chapters)."""

import pytest

from intro_gha.cost import billed_minutes, job_cost_mills, run_cost_mills
from intro_gha.matrix import check_limit, expand_matrix
from intro_gha.triggers import matches_filter, paths_trigger
from intro_gha.workflow import execution_waves


def test_matrix_3x3_is_9_jobs() -> None:
    """3 OS x 3 Python = 9 jobs (Chapter 10 running example)."""
    m = {"os": ["ubuntu", "windows", "macos"], "py": ["3.11", "3.12", "3.13"]}
    assert len(expand_matrix(m)) == 9


def test_matrix_exclude_and_include() -> None:
    """Exclude removes one combo; unmatched include adds one job."""
    m = {
        "os": ["a", "b"],
        "py": [1, 2],
        "exclude": [{"os": "b", "py": 1}],
        "include": [{"os": "c", "py": 3}],
    }
    assert len(expand_matrix(m)) == 4


def test_matrix_limit() -> None:
    """257 jobs breaches the 256 limit."""
    with pytest.raises(ValueError):
        check_limit([{}] * 257)


def test_paths_filter_double_star() -> None:
    """``sandbox/**`` matches nested files but not siblings."""
    assert paths_trigger(["sandbox/tally/add.py"], ["sandbox/**"])
    assert not paths_trigger(["README.md"], ["sandbox/**"])


def test_filter_negation_last_match_wins() -> None:
    """A later ``!`` pattern excludes."""
    assert not matches_filter("docs/a.md", ["**", "!docs/**"])
    assert matches_filter("src/a.py", ["**", "!docs/**"])


def test_single_star_stops_at_slash() -> None:
    """``*`` does not cross directory boundaries."""
    assert not matches_filter("a/b.py", ["*.py"])
    assert matches_filter("b.py", ["*.py"])


def test_billing_rounds_up_per_job() -> None:
    """61 s bills 2 min; on macOS that is 2 x 62 = 124 mills ($0.124)."""
    assert billed_minutes(61) == 2
    assert job_cost_mills(61, "macos") == 124
    assert run_cost_mills([(30, "linux"), (61, "windows")]) == 6 + 20


def test_execution_waves() -> None:
    """lint and test run in parallel, then build."""
    graph = {"lint": [], "test": [], "build": ["lint", "test"]}
    assert execution_waves(graph) == [["lint", "test"], ["build"]]
    with pytest.raises(ValueError):
        execution_waves({"a": ["b"], "b": ["a"]})
