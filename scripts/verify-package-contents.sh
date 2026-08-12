#!/usr/bin/env bash
# Guard the release zip actually contains a working plugin before it is
# attached to a release. Fails closed: any missing file, any stripped backend
# module, or any version mismatch aborts the release rather than publishing a
# broken or misversioned artifact. `jq` and `unzip` are preinstalled on the
# GitHub Actions runner.
#
# Usage: verify-package-contents.sh <zip-path> <tag>
set -euo pipefail

ZIP=${1:-}
TAG=${2:-}

if [ -z "$ZIP" ] || [ -z "$TAG" ]; then
  echo "usage: $0 <zip-path> <tag>" >&2
  exit 2
fi

if [ ! -f "$ZIP" ]; then
  echo "error: zip not found: $ZIP" >&2
  exit 2
fi

listing=$(unzip -Z1 "$ZIP")

for path in \
  ed-journal-monitor/package.json \
  ed-journal-monitor/plugin.json \
  ed-journal-monitor/main.py \
  ed-journal-monitor/dist/index.js
do
  # -F/-x: exact-line match. A substring match would let a longer path (or a
  # directory entry sharing the prefix) satisfy the check without the file
  # actually being present.
  printf '%s\n' "$listing" | grep -Fxq "$path" || {
    echo "::error::$path missing from $ZIP"; exit 1; }
done

# -E: at least one real backend .py file under modules/, not just the bare
# directory entry - a directory entry alone means every backend module was
# stripped while still leaving something that looks present. This is the
# check that had a real vacuous-check bug (#14): an earlier, weaker version
# matched the bare `bin/src/modules/` directory entry itself, with no .py
# files underneath, so a zip stripped of its entire backend still passed. It
# was caught by manual mutation testing, not by the guard at the time - which
# is why that mutation is now pinned as a pytest fixture instead of trusted
# to memory.
printf '%s\n' "$listing" | grep -Eq '^ed-journal-monitor/bin/src/modules/.+\.py$' || {
  echo "::error::no backend python modules in $ZIP"; exit 1; }

# Exact-line check on one specific, always-required module, in addition to
# the regex above. A regex weakened back toward matching a directory entry
# or an unrelated near-miss filename would still need to satisfy this pinned
# check, so vacuously passing the modules check alone cannot pass the guard.
printf '%s\n' "$listing" | grep -Fxq 'ed-journal-monitor/bin/src/modules/watcher.py' || {
  echo "::error::ed-journal-monitor/bin/src/modules/watcher.py missing from $ZIP"; exit 1; }

zipped=$(unzip -p "$ZIP" ed-journal-monitor/package.json | jq -r .version)
if [ "v$zipped" != "$TAG" ]; then
  echo "::error::bundled package.json is $zipped, expected ${TAG#v}"
  exit 1
fi

echo "$ZIP verified: version $zipped, all expected paths present"
