#!/usr/bin/env bash
set -e

VERSION=$1
[ -z "$VERSION" ] && { echo "Usage: $0 <version>  (e.g. $0 0.3.0)"; exit 1; }

# Validate semver-ish format
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Error: version must be x.y.z"; exit 1; }

echo "==> Bumping package.json to $VERSION"
npm version "$VERSION" --no-git-tag-version

echo ""
echo "==> Update CHANGELOG.md now:"
echo "    - Move [Unreleased] entries under a new [$VERSION] - $(date +%Y-%m-%d) header"
echo "    - Add a fresh empty [Unreleased] section above it"
echo ""
echo "Press enter when done..."
read -r

git add package.json package-lock.json CHANGELOG.md
git commit -m "chore: release v$VERSION"
git tag "v$VERSION"

echo ""
echo "==> Release v$VERSION tagged. To publish:"
echo "    git push && git push --tags"
echo ""
echo "    Pushing the tag triggers the Release workflow, which creates the"
echo "    GitHub Release (notes from CHANGELOG) and attaches the built .zip."
