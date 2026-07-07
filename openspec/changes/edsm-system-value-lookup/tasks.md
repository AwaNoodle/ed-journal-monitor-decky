## 1. Branch setup

- [x] 1.1 Create a feature branch or worktree (depends on `edsm-worth-scanning-lookup` being merged first)

## 2. Value fetch (read client)

- [x] 2.1 Write failing tests for an `estimated-value` fetch: success, unknown-system, and contained failure (→ neutral, no raise, no submission impact)
- [x] 2.2 Add the `estimated-value` GET to the EDSM read client, reusing UA + SSL context + no key
- [x] 2.3 Capture a sample `estimated-value` response and add a fixture; confirm the total + valued-bodies shape

## 3. Value summary + caching

- [x] 3.1 Write failing tests for the value summary: total + ranked priority bodies, and the no-valued-bodies (zero/empty) case
- [x] 3.2 Implement the summary derivation and cache it per system alongside the bodies result (same TTL/toggle)

## 4. Backend → frontend contract

- [x] 4.1 Extend the emitted per-system payload / `get_status` with value fields (`totalValue`, `priorityBodies`); add tests
- [x] 4.2 Update `src/types.d.ts` for the new value fields

## 5. Frontend UI

- [x] 5.1 Render the EDSM-sourced system value display (total + top priority bodies) in the Session metric area, with a neutral state when unavailable and live update on arrival

## 6. Verification & docs

- [x] 6.1 Run full pytest suite + lint/typecheck; all green
- [x] 6.2 Manually verify: arrival shows value + priority bodies; toggle-off makes no calls; submission unaffected on failure
- [x] 6.3 Update `README.md`, `CHANGELOG.md` (`[Unreleased]`), and `AGENTS.md`
- [ ] 6.4 Open a PR; merge via squash-and-rebase
