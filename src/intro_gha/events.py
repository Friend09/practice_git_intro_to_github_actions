"""A small executable model of "does this workflow fire for this event?".

The rules encoded here were checked against real runs in this repository (see
``fixtures/events_ch06_observed.json``) and GitHub Docs (verified 2026-10):

- ``push`` with only ``branches`` does not fire for tag pushes; with only ``tags`` it
  does not fire for branch pushes; with neither, both fire.
- ``paths`` / ``paths-ignore`` are applied to branch pushes only, never to tag pushes.
- ``pull_request`` defaults to the types opened, synchronize and reopened; ``branches``
  matches the *base* branch and ``paths`` the files changed in the PR.
- Events created with ``GITHUB_TOKEN`` start no runs, except ``workflow_dispatch`` and
  ``repository_dispatch``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from intro_gha.triggers import matches_filter, paths_trigger
from intro_gha.workflow import triggers

PR_DEFAULT_TYPES = {"opened", "synchronize", "reopened"}
TOKEN_EXEMPT = {"workflow_dispatch", "repository_dispatch"}


def _paths_ok(cfg: dict[str, Any], changed: list[str]) -> bool:
    """Apply ``paths`` / ``paths-ignore`` to a list of changed files."""
    if "paths" in cfg:
        return paths_trigger(changed, cfg["paths"])
    if "paths-ignore" in cfg:
        # Runs unless EVERY changed file is ignored.
        return any(not matches_filter(f, cfg["paths-ignore"]) for f in changed)
    return True


def _ref_ok(cfg: dict[str, Any], ref: str) -> bool:
    """Apply branch/tag filters to a full ref (``refs/heads/x`` or ``refs/tags/x``)."""
    is_tag = ref.startswith("refs/tags/")
    short = ref.split("/", 2)[2]
    has_b = "branches" in cfg or "branches-ignore" in cfg
    has_t = "tags" in cfg or "tags-ignore" in cfg
    own, other = (has_t, has_b) if is_tag else (has_b, has_t)
    if other and not own:
        return False  # only the other ref type is filtered, so this one never fires
    if not own:
        return True
    pos, neg = ("tags", "tags-ignore") if is_tag else ("branches", "branches-ignore")
    if pos in cfg:
        return matches_filter(short, cfg[pos])
    return not matches_filter(short, cfg[neg])


def would_fire(workflow: dict[str, Any], event: dict[str, Any]) -> bool:
    """Return True if ``workflow`` would create a run for ``event``.

    ``event`` keys: ``name`` (always), plus ``ref``, ``changed``, ``deleted``,
    ``action``, ``base`` and ``by_github_token`` where relevant.
    """
    name = event["name"]
    trig = triggers(workflow)
    if name not in trig:
        return False
    if event.get("by_github_token") and name not in TOKEN_EXEMPT:
        return False
    cfg = trig[name]
    if name == "push":
        if event.get("deleted"):
            return False
        ref = event["ref"]
        if not _ref_ok(cfg, ref):
            return False
        if ref.startswith("refs/tags/"):
            return True
        return _paths_ok(cfg, event.get("changed", []))
    if name == "pull_request":
        if event["action"] not in set(cfg.get("types", PR_DEFAULT_TYPES)):
            return False
        if "branches" in cfg and not matches_filter(event["base"], cfg["branches"]):
            return False
        return _paths_ok(cfg, event.get("changed", []))
    if name == "repository_dispatch":
        types = cfg.get("types")
        return types is None or event.get("action") in types
    return True


def _field(spec: str, lo: int, hi: int) -> set[int]:
    """Expand one cron field (``*``, ``*/n``, ``a-b``, ``a,b`` or ``a-b/n``)."""
    out: set[int] = set()
    for part in spec.split(","):
        rng, _, step = part.partition("/")
        step_n = int(step) if step else 1
        if rng == "*":
            start, end = lo, hi
        elif "-" in rng:
            a, b = rng.split("-")
            start, end = int(a), int(b)
        else:
            start = int(rng)
            end = hi if step else start
        out.update(range(start, end + 1, step_n))
    return out


def next_cron_run(expr: str, after: datetime) -> datetime:
    """Next UTC time strictly after ``after`` matching a 5-field cron expression.

    Day-of-month and day-of-week combine as in cron: if both are restricted a match on
    either is enough; if one is ``*`` only the other applies. Weekday 0 or 7 is Sunday.
    """
    mi, ho, dom, mon, dow = expr.split()
    minutes, hours = _field(mi, 0, 59), _field(ho, 0, 23)
    months, doms = _field(mon, 1, 12), _field(dom, 1, 31)
    dows = {d % 7 for d in _field(dow, 0, 7)}
    day = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(366 * 8 * 24 * 60):
        if day.month in months and _day_ok(day, dom, dow, doms, dows):
            for h in sorted(hours):
                for m in sorted(minutes):
                    cand = day.replace(hour=h, minute=m)
                    if cand >= (after + timedelta(minutes=1)).replace(second=0):
                        return cand
        day = (day + timedelta(days=1)).replace(hour=0, minute=0)
    raise ValueError(f"no run within 8 years for {expr!r}")


def _day_ok(day: datetime, dom: str, dow: str, doms: set[int], dows: set[int]) -> bool:
    """Cron day match: OR if both day fields are restricted, else the restricted one."""
    wd = (day.weekday() + 1) % 7  # Python Monday=0 -> cron Sunday=0
    dom_hit, dow_hit = day.day in doms, wd in dows
    if dom != "*" and dow != "*":
        return dom_hit or dow_hit
    return dom_hit and dow_hit
