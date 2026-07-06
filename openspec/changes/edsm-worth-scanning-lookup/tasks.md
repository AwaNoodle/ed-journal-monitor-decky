## 1. Branch setup

- [x] 1.1 Create a feature branch or worktree for this change (no direct commits to `main`)

## 2. EDSM read client (foundation)

- [x] 2.1 Write failing tests for the read client: known-system `bodies` fetch, unknown-to-EDSM result, and contained failure (network/timeout/non-200/malformed → "unavailable", no raise)
- [x] 2.2 Implement the read client for public `api-system-v1` GETs, reusing the custom User-Agent and `build_ssl_context()`, with no API-key dependency; separate from the write-only `forwarders/edsm_client.py`
- [x] 2.3 Confirm exact `api-system-v1/bodies` discovered/mapped field names against a captured sample response and add a fixture for tests

## 3. Per-system cache

- [x] 3.1 Write failing tests for TTL cache hit on re-entry (no new request) and miss after expiry (fresh request)
- [x] 3.2 Implement the per-system-name TTL cache used by the lookup path

## 4. Worth-scanning verdict

- [x] 4.1 Write failing tests over body-list fixtures for green (unknown / none tagged), yellow (partial), red (all discovered AND mapped), and neutral (disabled/in-flight/failed)
- [x] 4.2 Implement the verdict derivation (green/yellow/red/neutral) with EDSM attribution

## 5. Arrival trigger + toggle wiring

- [x] 5.1 Add the `edsm_lookups_enabled` setting (default off) with getter/setter callable, and persistence tests
- [x] 5.2 Write failing tests for the arrival consumer: one lookup per system entry, no duplicate for the current system, disabled-toggle short-circuits before any network call, and lookups never gate EDDN/EDSM-write
- [x] 5.3 Implement the arrival lookup as a `StreamConsumer` (observe FSDJump/Location), dedupe per system via session state, own the cache, and run async fire-and-forget
- [x] 5.4 Wire the consumer into `main.py` alongside existing consumers; ensure isolation (a read failure never affects submission)

## 6. Backend → frontend contract

- [x] 6.1 Emit the verdict payload (`{system, verdict, source:"edsm"}`) via a decky event and include it in `get_status`/session state for rehydrate-on-open; add tests
- [x] 6.2 Add the frontend callable(s)/types in `src/api.ts` and `src/types.d.ts` for the toggle setting and verdict payload

## 7. Frontend UI

- [x] 7.1 Add the EDSM auto-lookup toggle to the EDSM configuration section (with the "public data, no key needed" note), reflecting the persisted setting
- [x] 7.2 Render the EDSM-attributed worth-scanning chip in the Session metric area, mapping verdict → colour, with a neutral state when unavailable; update live on arrival

## 8. Verification & docs

- [x] 8.1 Run full pytest suite + lint/typecheck; all green
- [ ] 8.2 Manually verify on device (or with captured journals): arrival produces a chip, toggle-off makes no EDSM calls, EDDN/EDSM-write unaffected on read failure
- [x] 8.3 Update `README.md`, `CHANGELOG.md` (`[Unreleased]`), and `AGENTS.md` for the new read path, setting, and UI
- [ ] 8.4 Open a PR; merge via squash-and-rebase
