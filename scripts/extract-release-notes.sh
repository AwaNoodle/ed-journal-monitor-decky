#!/usr/bin/env bash
# Extract one version's section from CHANGELOG.md, for use as GitHub Release
# notes. Exits non-zero rather than emitting nothing, so a missing or
# misnamed section fails the release instead of publishing bare notes.
#
# Usage: extract-release-notes.sh <version> [changelog-path]
#   <version> is the bare version, no "v" prefix (e.g. 0.8.0)
set -euo pipefail

VERSION=${1:-}
CHANGELOG=${2:-CHANGELOG.md}

if [ -z "$VERSION" ]; then
  echo "usage: $0 <version> [changelog-path]" >&2
  exit 2
fi

if [ ! -f "$CHANGELOG" ]; then
  echo "error: changelog not found: $CHANGELOG" >&2
  exit 2
fi

# Literal prefix matching, not a regex: interpolating the version into a
# regex makes the dots wildcards, so 0.7.0 would also match 0X7X0.
#
# The section-end check matches "## " (any h2), not "## [" (only bracketed
# version headers): a bracket-less "## Heading" following a version section
# would otherwise never terminate it and get swallowed into the release
# notes. "### " subsections must not trip this - they are two characters
# longer than the "## " prefix being matched, so the prefix check on their
# first three characters ("###") never equals "## ".
notes=$(awk -v hdr="## [$VERSION]" '
  index($0, hdr) == 1 { flag = 1; next }
  flag && index($0, "## ") == 1 { exit }
  flag { print }
' "$CHANGELOG")

if ! printf '%s' "$notes" | grep -q '[^[:space:]]'; then
  echo "error: no non-empty '## [$VERSION]' section in $CHANGELOG" >&2
  echo "hint: the header must read exactly '## [$VERSION] - YYYY-MM-DD'" >&2
  exit 1
fi

printf '%s\n' "$notes"
