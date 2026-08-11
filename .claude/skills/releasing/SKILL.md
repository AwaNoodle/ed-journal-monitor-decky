---
name: releasing
description: Use when cutting, tagging, or publishing a release of this plugin - bumping the version, rolling up the CHANGELOG, creating the release PR, tagging, or diagnosing a Release workflow run that failed or produced no GitHub Release.
---

# Releasing

How to cut a release of ed-journal-monitor-decky. The version users see in Decky comes from
`package.json`, the GitHub Release notes come from `CHANGELOG.md`, and everything after the tag
push is automated by `.github/workflows/release.yml`.

## Quick reference

| Step | Command |
|---|---|
| Verify | `npm run lint:ts` · `npm run lint:py` |
| Branch | `git checkout -b <version>-release` |
| Bump | `npm version <version> --no-git-tag-version` |
| Roll up the changelog | edit `CHANGELOG.md` (see below) |
| Commit | `git add package.json package-lock.json CHANGELOG.md && git commit -m "chore: release v<version>"` |
| PR | `gh pr create --title "chore: release v<version>"` |
| Gate | Wait for the Build workflow to pass on the PR |
| Merge | Squash merge into `main` |
| Tag the merged commit | `git checkout main && git pull --ff-only && git tag v<version>` |
| Publish | `git push --tags` |

## Preconditions

- Every change intended for this release is already merged into `main`.
- `main` is pulled and the working tree is clean.
- `npm run lint:ts` and `npm run lint:py` both pass locally (`lint:py` also runs the full pytest
  suite). CI re-runs these on the tag, so a failure here becomes a failed release, not a caught one.
- `CHANGELOG.md`'s `[Unreleased]` section has an entry for each change in the release. If it's
  empty or thin, the GitHub Release notes will be too - the workflow copies that section verbatim.

## Choosing the version

Semver `x.y.z`, judged from the `[Unreleased]` entries: breaking user-visible behaviour → major,
new features → minor, fixes only → patch.

## Cutting the release

Release commits go through a PR like any other change - `main` takes no direct pushes.

1. Branch off up-to-date `main`: `git checkout -b <version>-release`.

2. Bump the version. Use `npm version` rather than hand-editing, so `package-lock.json` moves too:

   ```
   npm version <version> --no-git-tag-version
   ```

   `--no-git-tag-version` matters - the tag must not exist yet (see step 5 for why).

3. Roll up `CHANGELOG.md`:
   - Rename `## [Unreleased]` to `## [<version>] - <YYYY-MM-DD>` (today's date).
   - Add a fresh empty `## [Unreleased]` section above it.

4. Commit the three files together:

   ```
   git add package.json package-lock.json CHANGELOG.md
   git commit -m "chore: release v<version>"
   ```

5. Open the PR (`chore: release v<version>`). Body should state the version bump, the changelog
   roll-up, a one-line summary of what's in the release, and the local verification results.

   **Wait for the Build workflow to go green before merging.** `.github/workflows/build.yml` runs
   on every PR and executes the same lint → ruff → pytest → `npm run package` sequence the Release
   workflow will run on the tag, on the same Node 20 / Python 3.9 setup - so it is a dry run of
   the tag build, against the bumped `package.json`. Merging on red commits you to a release run
   that fails *after* the tag exists, which is the awkward direction to recover from.

   Build does not cover the release-specific steps, which only ever run on the tag: the `awk`
   extraction of the changelog section, the zip rename, and `gh release create`. A malformed
   `## [<version>]` header passes Build and surfaces only as bare release notes on the published
   Release - so proofread that section in the PR diff by eye.

6. Squash merge. **Do not tag on this branch** - squash-merging discards the branch commit, so the
   tag has to land on the commit that ends up on `main`. Build runs once more on the merge push;
   let it go green before tagging.

## Publishing

```
git checkout main && git pull --ff-only
git tag v<version>
git push --tags
```

Pushing the tag triggers `.github/workflows/release.yml`, which lints, runs the tests, packages,
**creates the GitHub Release** with notes extracted from the matching `CHANGELOG.md` section, and
attaches `ed-journal-monitor-decky-v<version>.zip`.

Do not create the GitHub Release by hand for a normal tag push - the workflow does it. (It also
still handles a manually-published Release via its `release: published` trigger, where it skips
creation and only attaches the asset. A Release the workflow creates itself uses `GITHUB_TOKEN`,
which deliberately does not re-trigger that job, so there's no double run.)

Watch the run: `gh run watch` or `gh run list --workflow=release.yml`.

## Verifying

- `gh release view v<version>` - notes match the changelog section, zip asset attached.
- The zip is named `ed-journal-monitor-decky-v<version>.zip` (tag included, `v` and all).
- `package.json` on `main` reads `<version>` - this is what Decky displays on-device.

## Common mistakes

| Mistake | Consequence |
|---|---|
| Tagging before bumping `package.json` | Decky shows the old version on-device; the zip is built from the tag |
| Tagging on the release branch | Tag points at the pre-squash commit, which isn't on `main` |
| Hand-editing `package.json` instead of `npm version` | `package-lock.json` drifts out of sync |
| Empty or missing `## [<version>]` changelog section | Workflow falls back to bare notes: `Release v<version>` |
| Wrong changelog header format | The `awk` extractor matches `^## \[<version>\]` exactly; anything else yields the fallback notes |
| Hand-creating the GitHub Release, then pushing the tag | Duplicate/conflicting release; `gh release create` in the workflow fails |
| Pushing with `git push` only | Tags are not pushed by default - no tag, no workflow, no release |
| Merging the release PR on a red Build | The tag build fails the same way, but after the tag exists |
