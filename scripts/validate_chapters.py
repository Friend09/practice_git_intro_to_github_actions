#!/usr/bin/env python3
"""Structural validator for chapters in learning_modules/.

Run it after any chapter edit and before committing:

    uv run python scripts/validate_chapters.py               # all chapters
    uv run python scripts/validate_chapters.py chapter_06    # prefix match

Per chapter it performs five checks:

1. Header block   -- the required ``**Field:**`` metadata lines from
                     .github/instructions/chapter-content.instructions.md are
                     present near the top of the file. Failures are ERRORS.
2. Heading drift  -- diffs ##/### headings against the committed version
                     (``git show HEAD:<file>``) and lists dropped/added
                     headings. Reported as WARNINGS so the reviewer can
                     confirm each change was intentional.
3. Link integrity -- every relative file link resolves to an existing file,
                     and every in-file anchor link (TOC entries, ``(#aX-...)``
                     appendix references) has a matching heading. Failures are
                     ERRORS. TOC coverage is enforced by this check because
                     TOC entries are anchor links.
4. Math format    -- every ``$$`` display block opens and closes on the same
                     physical line (Marked 2 compatibility). Failures are
                     ERRORS.
5. Artifact refs  -- the notebook/script paths named in the header block
                     exist on disk unless the field value is ``-``, and any
                     "Chapter XX Section N" reference inside the paired
                     notebooks matches a ``## N.`` heading in the chapter
                     (the section-renumbering tripwire). Failures are ERRORS.

Exit status is non-zero if any ERROR was found; warnings alone exit 0.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAPTERS_DIR = REPO_ROOT / "learning_modules"
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"

REQUIRED_HEADER_FIELDS = [
    "Reading Time",
    "Prerequisites",
    "Practice Notebook",
    "Reference Notebook",
    "Script",
    "Book Reference",
    "Depth",
    "Default Runtime",
]

HEADING_RE = re.compile(r"^(#{2,3})\s+(.*)$")
ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
ANCHOR_LINK_RE = re.compile(r"\[[^\]]*\]\(#([^)]+)\)")
FILE_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#][^)]*)\)")
HEADER_FIELD_RE = re.compile(r"^\*\*([^*]+):\*\*\s*(.*)$")
ARTIFACT_PATH_RE = re.compile(r"`((?:notebooks|labs)/[^`]+)`")
CHAPTER_SECTION_REF_RE = re.compile(r"Chapter\s*(\d{1,2})\D{0,3}Section\s*(\d{1,2})")


def strip_code_fences(text: str) -> list[str]:
    """Return the lines of ``text`` that sit outside fenced code blocks."""
    lines = []
    fence = None
    for line in text.splitlines():
        stripped = line.lstrip()
        match = re.match(r"^(`{3,}|~{3,})", stripped)
        if match:
            marker = match.group(1)[0] * 3
            if fence is None:
                fence = marker
            elif stripped.startswith(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return lines


def extract_headings(text: str, all_levels: bool = False) -> list[str]:
    """Extract heading titles from markdown, ignoring code fences."""
    pattern = ANY_HEADING_RE if all_levels else HEADING_RE
    headings = []
    for line in strip_code_fences(text):
        match = pattern.match(line)
        if match:
            headings.append(match.group(2).strip())
    return headings


def github_slug(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor slug algorithm."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)  # unwrap links
    text = re.sub(r"\$[^$]*\$", "", text)  # drop inline LaTeX math
    text = "".join(
        ch for ch in text if not unicodedata.category(ch).startswith("So")
    )
    text = text.lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def collapse(slug: str) -> str:
    """Normalize a slug for tolerant comparison across generators."""
    slug = slug.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", slug)


def committed_text(rel_path: str) -> str | None:
    """Return the HEAD version of a repo-relative file, or None if untracked."""
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def chapter_number(path: Path) -> str | None:
    """Extract the two-digit chapter number from a chapter filename, if any."""
    match = re.match(r"chapter_(\d{2})", path.name)
    return match.group(1) if match else None


def top_level_section_numbers(text: str) -> set[int]:
    """Collect N for every ``## N.`` heading in the chapter."""
    numbers = set()
    for heading in extract_headings(text):
        match = re.match(r"(\d{1,2})\.", heading)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def check_header_block(text: str, errors: list[str]) -> None:
    """Verify the required chapter metadata fields appear near the top."""
    head = text.splitlines()[:20]
    found = {
        match.group(1).strip()
        for line in head
        if (match := HEADER_FIELD_RE.match(line.strip()))
    }
    for field in REQUIRED_HEADER_FIELDS:
        if field not in found:
            errors.append(f"missing header field: **{field}:**")


def check_headings(path: Path, text: str, warnings: list[str]) -> None:
    """Warn about headings dropped or added relative to the HEAD version."""
    old = committed_text(str(path.relative_to(REPO_ROOT)))
    if old is None:
        return
    old_headings = extract_headings(old)
    new_headings = extract_headings(text)
    for heading in old_headings:
        if heading not in new_headings:
            warnings.append(f"dropped heading: {heading!r}")
    for heading in new_headings:
        if heading not in old_headings:
            warnings.append(f"added heading:   {heading!r}")


def check_links(path: Path, text: str, errors: list[str]) -> None:
    """Verify relative file links and in-file anchor links resolve."""
    slugs = set()
    slug_counts: dict[str, int] = {}
    for heading in extract_headings(text, all_levels=True):
        slug = github_slug(heading)
        n = slug_counts.get(slug, 0)
        slug_counts[slug] = n + 1
        slugs.add(slug if n == 0 else f"{slug}-{n}")
    collapsed_slugs = {collapse(s) for s in slugs}

    body = "\n".join(strip_code_fences(text))
    for anchor in ANCHOR_LINK_RE.findall(body):
        candidate = anchor.lower()
        if candidate not in slugs and collapse(candidate) not in collapsed_slugs:
            errors.append(f"anchor link with no matching heading: #{anchor}")
    for target in FILE_LINK_RE.findall(body):
        if re.match(r"^[a-z]+:", target) or target.startswith("mailto"):
            continue
        target_path = (path.parent / target.split("#")[0]).resolve()
        if not target_path.exists():
            errors.append(f"broken relative link: {target}")


def check_math_blocks(text: str, errors: list[str]) -> None:
    """Verify every ``$$`` display block opens and closes on one line."""
    for line in strip_code_fences(text):
        if line.count("$$") % 2 != 0:
            errors.append(
                f"multi-line $$ block (must be one physical line): "
                f"{line.strip()[:60]!r}"
            )


def check_artifact_refs(path: Path, text: str, errors: list[str]) -> None:
    """Verify header-block artifact paths exist and notebook refs resolve."""
    head = text.splitlines()[:20]
    for line in head:
        match = HEADER_FIELD_RE.match(line.strip())
        if not match:
            continue
        for artifact in ARTIFACT_PATH_RE.findall(match.group(2)):
            if not (REPO_ROOT / artifact).exists():
                errors.append(f"header references missing artifact: {artifact}")

    number = chapter_number(path)
    if number is None:
        return
    sections = top_level_section_numbers(text)
    for nb_path in NOTEBOOKS_DIR.glob(f"*_{number}*.ipynb"):
        try:
            nb = json.loads(nb_path.read_text())
        except json.JSONDecodeError:
            errors.append(f"notebook does not parse as JSON: {nb_path.name}")
            continue
        content = "".join(
            "".join(cell.get("source", [])) for cell in nb.get("cells", [])
        )
        for chap_ref, sec_ref in CHAPTER_SECTION_REF_RE.findall(content):
            if int(chap_ref) != int(number):
                continue
            if int(sec_ref) not in sections:
                errors.append(
                    f"{nb_path.name} references Chapter {number} "
                    f"Section {sec_ref}, which no longer exists"
                )


def validate(path: Path) -> tuple[list[str], list[str]]:
    """Run all checks on one chapter file; return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text()
    check_header_block(text, errors)
    check_headings(path, text, warnings)
    check_links(path, text, errors)
    check_math_blocks(text, errors)
    check_artifact_refs(path, text, errors)
    return errors, warnings


def main() -> int:
    """CLI entry point: validate selected (or all) chapters and report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "chapters",
        nargs="*",
        help="chapter filename prefixes to validate (default: all .md files)",
    )
    args = parser.parse_args()

    candidates = sorted(CHAPTERS_DIR.glob("chapter_*.md"))
    if args.chapters:
        candidates = [
            p
            for p in candidates
            if any(p.name.startswith(prefix) for prefix in args.chapters)
        ]
        if not candidates:
            print(f"no chapter files match: {args.chapters}", file=sys.stderr)
            return 2

    total_errors = 0
    for path in candidates:
        errors, warnings = validate(path)
        if errors or warnings:
            print(f"\n{path.name}")
            for warning in warnings:
                print(f"  WARN  {warning}")
            for error in errors:
                print(f"  ERROR {error}")
        total_errors += len(errors)

    print(
        f"\nchecked {len(candidates)} file(s): "
        f"{total_errors} error(s). "
        "Review WARN heading drops -- each must be intentional."
    )
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
