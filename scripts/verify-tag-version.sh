#!/usr/bin/env bash
# Guard the pushed tag matches package.json's version. package.json ships
# inside the zip and is read at runtime for the EDDN softwareVersion header,
# so a tag/package.json mismatch publishes a plugin that misreports itself.
# Fails closed before the expensive build/test/package steps run.
#
# Usage: verify-tag-version.sh <tag> [package-json-path]
set -euo pipefail

TAG=${1:-}
PACKAGE_JSON=${2:-package.json}

if [ -z "$TAG" ]; then
  echo "usage: $0 <tag> [package-json-path]" >&2
  exit 2
fi

if [ ! -f "$PACKAGE_JSON" ]; then
  echo "error: package.json not found: $PACKAGE_JSON" >&2
  exit 2
fi

# jq rather than `node -p`: keeps this script's only dependency the same one
# verify-package-contents.sh already requires, and testable without a
# guaranteed node on the machine running the tests.
pkg=$(jq -r .version "$PACKAGE_JSON")

if [ "v$pkg" != "$TAG" ]; then
  echo "::error::tag $TAG does not match package.json version $pkg"
  exit 1
fi

echo "tag $TAG matches package.json $pkg"
