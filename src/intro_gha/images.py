"""Container image reference rules used in Chapter 12 (GHCR naming and digests)."""

from __future__ import annotations

import re

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def ghcr_ref(
    owner: str, name: str, tag: str | None = None, digest: str | None = None
) -> str:
    """Build a ``ghcr.io`` reference, lowercasing the owner as GHCR requires.

    Pass ``digest`` for an immutable reference (``name@sha256:...``) or ``tag`` for a
    movable one (``name:tag``). Exactly one of the two must be given.
    """
    if (tag is None) == (digest is None):
        raise ValueError("give exactly one of tag or digest")
    base = f"ghcr.io/{owner.lower()}/{name}"
    if digest is not None:
        if not DIGEST_RE.match(digest):
            raise ValueError(f"not a sha256 digest: {digest!r}")
        return f"{base}@{digest}"
    return f"{base}:{tag}"


def repository_name_ok(reference: str) -> bool:
    """Docker's rule that the repository path of a reference is all lowercase.

    The registry host (before the first ``/``) and any ``:tag`` or ``@digest`` suffix
    are not part of the repository path.
    """
    _, _, rest = reference.partition("/")
    path = rest.split("@", 1)[0]
    head, _, last = path.rpartition("/")
    last = last.split(":", 1)[0]
    repo = f"{head}/{last}" if head else last
    return repo == repo.lower()
