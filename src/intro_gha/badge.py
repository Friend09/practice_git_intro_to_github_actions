"""Build GitHub Actions status-badge URLs and Markdown (Chapter 03).

A workflow status badge is an SVG served at
``https://github.com/OWNER/REPO/actions/workflows/FILE/badge.svg``. It shows the
conclusion of the **latest run** that matches the optional ``branch`` and ``event``
query filters; with no filter it follows the default branch. A filter that matches no
run renders ``no status`` (verified against a live repository, 2026-10).
"""

from __future__ import annotations

from urllib.parse import quote, urlencode


def badge_url(
    repo: str, workflow_file: str, branch: str | None = None, event: str | None = None
) -> str:
    """Return the badge SVG URL for ``workflow_file`` in ``repo``.

    ``branch`` and ``event`` are added as query parameters only when given.
    """
    base = f"https://github.com/{repo}/actions/workflows/{workflow_file}/badge.svg"
    params = {k: v for k, v in (("branch", branch), ("event", event)) if v}
    return f"{base}?{urlencode(params, safe='/')}" if params else base


def badge_markdown(repo: str, workflow_file: str, label: str, **filters: str) -> str:
    """Return README Markdown: the badge image linking to the workflow's run list."""
    runs = f"https://github.com/{repo}/actions/workflows/{quote(workflow_file)}"
    return f"[![{label}]({badge_url(repo, workflow_file, **filters)})]({runs})"


def badge_status(svg: str) -> str:
    """Extract the status word (``passing``, ``failing``, ``no status``) from SVG."""
    start = svg.index("<title>") + len("<title>")
    title = svg[start : svg.index("</title>", start)]
    return title.rsplit(" - ", 1)[1]
