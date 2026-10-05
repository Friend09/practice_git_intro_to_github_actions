"""Pin every remote ``uses: owner/repo@tag`` in .github/workflows to its commit SHA.

Usage: ``uv run python scripts/pin_actions.py [--check]``. Each pinned line keeps the
original tag as a trailing comment (``uses: owner/repo@<sha> # v7``) so a human or
Dependabot can see which version it is. Workflows listed in ``EXEMPT`` teach unpinned
forms on purpose (Chapter 04) and are left alone.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEMPT = {
    "ch04-uses-forms.yml",
    "ch04-bad-ref.yml",
    "ch16-sha-policy.yml",
    "ch16-tag-object-sha.yml",
}
LINE = re.compile(r"^(?P<indent>\s*(?:-\s+)?uses:\s*)(?P<ref>[^\s#]+)(?P<rest>.*)$")
SHA = re.compile(r"^[0-9a-f]{40}$")


@cache
def resolve(repo: str, tag: str) -> str:
    """Resolve ``repo@tag`` to a commit SHA, dereferencing annotated tags."""
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/ref/tags/{tag}"],
        check=True, capture_output=True, text=True,
    ).stdout
    obj = json.loads(out)["object"]
    if obj["type"] == "tag":
        out = subprocess.run(
            ["gh", "api", f"repos/{repo}/git/tags/{obj['sha']}"],
            check=True, capture_output=True, text=True,
        ).stdout
        obj = json.loads(out)["object"]
    return obj["sha"]


def pin_file(path: Path, check_only: bool) -> int:
    """Rewrite one workflow file; return how many references need (or got) pinning."""
    changed = 0
    lines = path.read_text().splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = LINE.match(line.rstrip("\n"))
        if not m:
            continue
        ref = m["ref"]
        if ref.startswith(("./", "docker://")) or "@" not in ref:
            continue
        repo_path, _, version = ref.partition("@")
        if SHA.match(version):
            continue
        repo = "/".join(repo_path.split("/")[:2])
        changed += 1
        if not check_only:
            sha = resolve(repo, version)
            lines[i] = f"{m['indent']}{repo_path}@{sha} # {version}\n"
    if changed and not check_only:
        path.write_text("".join(lines))
    return changed


def is_commit(repo: str, sha: str) -> bool:
    """True if ``sha`` is a commit in ``repo`` (a tag-object SHA is not)."""
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/commits/{sha}"], capture_output=True, text=True
    )
    return r.returncode == 0


def verify() -> int:
    """Check that every pinned SHA is a commit, not an annotated tag object."""
    bad = 0
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        if path.name in EXEMPT:
            continue
        for line in path.read_text().splitlines():
            m = LINE.match(line)
            if not m or "@" not in m["ref"]:
                continue
            if m["ref"].startswith(("./", "docker://")):
                continue
            repo_path, _, sha = m["ref"].partition("@")
            repo = "/".join(repo_path.split("/")[:2])
            if SHA.match(sha) and not is_commit(repo, sha):
                print(f"NOT A COMMIT: {path.name}: {m['ref']}")
                bad += 1
    print(f"verify: {bad} pin(s) are not commits")
    return 1 if bad else 0


def main() -> None:
    """CLI entry point."""
    if "--verify" in sys.argv:
        sys.exit(verify())
    check = "--check" in sys.argv
    total = 0
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        if path.name in EXEMPT:
            continue
        n = pin_file(path, check)
        if n:
            print(f"{'would pin' if check else 'pinned'} {n:2d} in {path.name}")
        total += n
    print(f"total: {total}")
    sys.exit(1 if (check and total) else 0)


if __name__ == "__main__":
    main()
