#!/usr/bin/env bash
# Validate $VERSION as MAJOR.MINOR.PATCH[-pre] and write step outputs.
set -euo pipefail
re='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-([0-9A-Za-z.-]+))?$'
if [[ ! "${VERSION}" =~ $re ]]; then
  echo "::error title=Not a semantic version::'${VERSION}' is not MAJOR.MINOR.PATCH"
  exit 1
fi
{
  echo "normalized=${VERSION}"
  echo "major=${BASH_REMATCH[1]}"
  echo "minor=${BASH_REMATCH[2]}"
  echo "patch=${BASH_REMATCH[3]}"
  if [[ -n "${BASH_REMATCH[5]:-}" ]]; then echo "is_prerelease=true"; else echo "is_prerelease=false"; fi
} >> "${GITHUB_OUTPUT}"
echo "parsed ${VERSION}"
