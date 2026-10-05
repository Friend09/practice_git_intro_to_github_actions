"""Semantic Versioning helpers for release automation (Chapter 14)."""

from __future__ import annotations

import re
from dataclasses import dataclass

SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<pre>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
TAG_GLOB = "v[0-9]*.[0-9]*.[0-9]*"


@dataclass(frozen=True)
class Version:
    """A parsed semantic version (build metadata is not supported)."""

    major: int
    minor: int
    patch: int
    pre: str | None = None

    def __str__(self) -> str:
        """Render as ``MAJOR.MINOR.PATCH[-pre]``."""
        base = f"{self.major}.{self.minor}.{self.patch}"
        return f"{base}-{self.pre}" if self.pre else base

    def bump(self, part: str) -> Version:
        """Return the next ``major``, ``minor`` or ``patch`` version (drops any pre)."""
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, 0)
        if part == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"unknown part: {part}")

    def sort_key(self) -> tuple:
        """Ordering key: numbers first; a version with a pre-release sorts lower."""
        pre_key = (1,) if self.pre is None else (0, *_pre_ids(self.pre))
        return (self.major, self.minor, self.patch, pre_key)


def _pre_ids(pre: str) -> tuple:
    """Pre-release identifiers: numeric ones compare as numbers, below text ones."""
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split("."))


def parse(text: str) -> Version:
    """Parse ``text`` (no leading ``v``) or raise ValueError."""
    m = SEMVER_RE.match(text)
    if not m:
        raise ValueError(f"not a semantic version: {text!r}")
    return Version(int(m["major"]), int(m["minor"]), int(m["patch"]), m["pre"])


def tag_to_version(tag: str) -> Version:
    """Parse a release tag like ``v0.1.0`` (the ``v`` is required)."""
    if not tag.startswith("v"):
        raise ValueError(f"tag must start with 'v': {tag!r}")
    return parse(tag[1:])


def latest(versions: list[str]) -> str:
    """Return the highest of the given version strings under SemVer ordering."""
    return max(versions, key=lambda v: parse(v).sort_key())
