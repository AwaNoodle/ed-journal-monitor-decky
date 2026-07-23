## 1. Branch setup

- [x] 1.1 Create a feature branch or worktree (depends on `edsm-worth-scanning-lookup` being merged first)

## 2. Sphere-systems read

- [x] 2.1 Write failing tests for a `sphere-systems` fetch: success with primary-star info, and contained failure (→ unavailable, no raise, no submission impact)
- [x] 2.2 Add the `sphere-systems` GET (bounded radius, primary-star request) to the EDSM read client
- [x] 2.3 Capture a sample `sphere-systems` response and add a fixture; confirm the primary-star scoopability field shape

## 3. Nearest scoopable computation

- [x] 3.1 Write failing tests: nearest scoopable found, none-found-within-radius, and disabled-toggle short-circuit
- [x] 3.2 Implement the nearest-scoopable-star computation (closest scoopable primary star → name/distance/class)

## 4. On-demand callable

- [x] 4.1 Add a backend callable to run the lookup on demand and return the result; add tests (including toggle-off returns disabled without a request)
- [x] 4.2 Add the callable + result type to `src/api.ts` and `src/types.d.ts`

## 5. Frontend UI

- [x] 5.1 Add the "nearest scoopable star" action + result display to the panel, with in-flight / none-found / unavailable / disabled states, labelled EDSM-sourced

## 6. Verification & docs

- [x] 6.1 Run full pytest suite + lint/typecheck; all green
- [x] 6.2 Manually verify: action returns a nearby scoopable star; none-found handled; toggle-off makes no call; submission unaffected
- [x] 6.3 Update `README.md`, `CHANGELOG.md` (`[Unreleased]`), and `AGENTS.md`
- [ ] 6.4 Open a PR; merge via squash-and-rebase
