#!/usr/bin/env bash
# Guard the tagged commit is on main. A tag matching v* fires the release
# workflow wherever it points, so without this a tag on an unmerged branch
# would publish a release from code that never went through a PR. Fails
# closed: any ancestry check that can't run treated as "not on main".
#
# Usage: verify-tag-on-main.sh <sha> [tag-label] [remote] [branch]
#   <tag-label> is cosmetic only, e.g. v1.2.3 - it names the pushed tag in the
#   annotation so a failed run points at what was pushed, not just its SHA.
set -euo pipefail

SHA=${1:-}
TAG_LABEL=${2:-}
REMOTE=${3:-origin}
BRANCH=${4:-main}

if [ -z "$SHA" ]; then
  echo "usage: $0 <sha> [tag-label] [remote] [branch]" >&2
  exit 2
fi

# What the ancestry failure gets called in output - the tag if the caller
# gave one (a bare SHA in a CI log is hard to trace back to the release that
# failed), the SHA alone otherwise.
described_as=$SHA
if [ -n "$TAG_LABEL" ]; then
  described_as="$TAG_LABEL ($SHA)"
fi

# Compare against FETCH_HEAD, not "$REMOTE/$BRANCH": checking out a tag
# leaves a narrow fetch refspec, under which `git fetch` never creates
# refs/remotes/origin/main. Naming it would abort with "Needed a single
# revision" and read as "not on main" - failing every legitimate release for
# the wrong reason. This also requires the caller's clone to have real
# history (fetch-depth: 0 in CI) - a shallow clone can report a wrong answer
# when the merge base lies beyond the fetched depth.
git fetch --no-tags "$REMOTE" "$BRANCH"
if ! git merge-base --is-ancestor "$SHA" FETCH_HEAD; then
  echo "::error::$described_as is not on $BRANCH - releases must be tagged on $BRANCH"
  exit 1
fi

echo "$described_as is on $BRANCH"
