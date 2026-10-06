"""Fill the ``<!-- toc-start -->`` block of each chapter from its ``## N.`` headings.

Usage: ``uv run python scripts/gen_toc.py [chapter_XX ...]``. Anchors use the same
slug algorithm as ``validate_chapters.py``, so link integrity holds by construction.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_chapters import github_slug, strip_code_fences  # noqa: E402

# Marked 2 auto-expands ``<!-- TOC -->`` and duplicates the list, so use toc-start/end.
# The old markers are still matched so existing chapters migrate on the next run.
START, END = "<!-- toc-start -->", "<!-- toc-end -->"
TOC_RE = re.compile(r"<!-- (?:TOC|toc-start) -->.*?<!-- (?:/TOC|toc-end) -->", re.S)


def build_toc(text: str) -> str:
    """Return the TOC block for ``text`` (numbered sections plus Appendix A.x)."""
    lines = []
    for line in strip_code_fences(text):
        m = re.match(r"^(##|###)\s+((?:\d+\.|A\.\d+)\s.*)$", line)
        if not m:
            continue
        title = m.group(2).strip()
        indent = "   " if m.group(1) == "###" else ""
        lines.append(f"{indent}- [{title}](#{github_slug(title)})")
    return f"{START}\n" + "\n".join(lines) + f"\n{END}"


def main() -> None:
    """Rewrite the TOC in the selected (or all) chapters."""
    prefixes = sys.argv[1:]
    for path in sorted((ROOT / "learning_modules").glob("chapter_*.md")):
        if prefixes and not any(path.name.startswith(p) for p in prefixes):
            continue
        text = path.read_text()
        if not TOC_RE.search(text):
            continue
        toc = build_toc(text)
        path.write_text(TOC_RE.sub(lambda _m, toc=toc: toc, text))
        print("toc:", path.name)


if __name__ == "__main__":
    main()
