#!/usr/bin/env bash
# Usage: scripts/finish.sh 03 04 ...  -> TOC, validate, execute+clear lab notebooks, lint, test.
set -euo pipefail
cd "$(dirname "$0")/.."
for n in "$@"; do
  uv run python scripts/gen_toc.py "chapter_$n"
  uv run python scripts/validate_chapters.py "chapter_$n" | tail -1
  for nb in notebooks/lab_${n}_*.ipynb; do
    uv run jupyter nbconvert --to notebook --execute --inplace "$nb" >/dev/null 2>&1 \
      || { echo "NOTEBOOK FAILED: $nb"; exit 1; }
    uv run jupyter nbconvert --ClearOutputPreprocessor.enabled=True --to notebook \
      --inplace "$nb" >/dev/null 2>&1
  done
  uv run python labs/lab_${n}_*.py >/dev/null
done
uv run ruff check . && uv run pytest 2>&1 | tail -1
