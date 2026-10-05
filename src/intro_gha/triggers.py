"""Model GitHub's event filters: branch/tag globs and ``paths`` filters."""

from __future__ import annotations

import re


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a GitHub filter glob into a regex.

    ``*`` matches anything except ``/``; ``**`` matches anything including ``/``;
    ``?`` matches one character except ``/``.
    """
    out = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern[i : i + 2] == "**":
            out.append(".*")
            i += 2
            continue
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches_filter(value: str, patterns: list[str]) -> bool:
    """Apply a GitHub include/exclude filter list to one branch name or path.

    A leading ``!`` excludes. The last matching pattern wins, as on GitHub.
    A list with only negative patterns matches nothing (GitHub requires a positive).
    """
    result = False
    for pat in patterns:
        negate = pat.startswith("!")
        if glob_to_regex(pat[1:] if negate else pat).match(value):
            result = not negate
    return result


def paths_trigger(changed: list[str], paths: list[str]) -> bool:
    """Return True if ANY changed file matches the ``paths`` filter."""
    return any(matches_filter(f, paths) for f in changed)
