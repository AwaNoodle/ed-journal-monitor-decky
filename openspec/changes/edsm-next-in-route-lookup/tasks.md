## 1. Branch setup

- [x] 1.1 Create a feature branch or worktree (depends on `edsm-worth-scanning-lookup`; composes with `edsm-system-value-lookup` if present)

## 2. Next-in-route determination

- [x] 2.1 Write failing tests for next-hop derivation from `NavRoute.json`: mid-route next hop, final hop (none), no/empty route, off-route, and advance-after-jump
- [x] 2.2 Implement next-hop tracking from the already-parsed NavRoute data, matched against the current system (name/SystemAddress), updating on route change and each jump

## 3. Next-hop preview lookup

- [x] 3.1 Write failing tests: preview produced (scoopability + verdict, value when available), cache reuse for the next system, and neutral state when disabled/no-hop/failed
- [x] 3.2 Implement the next-hop lookup reusing the per-system read + TTL cache, composing value optionally; non-blocking and contained on failure

## 4. Backend → frontend contract

- [x] 4.1 Add a `nextHop` preview object to the emitted status/session payload (rehydrate-on-open supported); add tests
- [x] 4.2 Update `src/types.d.ts` for the next-hop preview fields

## 5. Frontend UI

- [x] 5.1 Render the EDSM-sourced "next hop" chip in the Session metric area (next system + scoopability, plus verdict/value when available), with neutral states and live update after each jump

## 6. Verification & docs

- [x] 6.1 Run full pytest suite + lint/typecheck; all green
- [x] 6.2 Manually verify (captured journals): plotting a route shows the next-hop preview; it advances on jump; no route → neutral; submission unaffected on failure
- [x] 6.3 Update `README.md`, `CHANGELOG.md` (`[Unreleased]`), and `AGENTS.md`
- [ ] 6.4 Open a PR; merge via squash-and-rebase
