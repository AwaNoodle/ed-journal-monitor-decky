## 1. Shared groundwork

- [x] 1.1 Lift `_build_ssl_context()` out of `submitter.py` into a shared module (e.g. `src/modules/ssl_context.py`); import it from `submitter.py` unchanged; add a test that EDDN submission still builds its context via the shared helper (EDDN behavior byte-for-byte unchanged)
- [x] 1.2 Extend the `StreamConsumer` protocol (introduced by session-dashboard) with `name: str`, `get_stats() -> dict`, `on_session_start()`, and `on_session_stop()`; give the session-dashboard accumulator no-op/zero implementations where it has none; add a test asserting the watcher fan-out still calls `observe` for every consumer and that `main.py` invokes `on_session_start`/`on_session_stop` across all consumers

## 2. EDSM API client (backend, TDD)

- [x] 2.1 Write `tests/test_edsm_client.py` covering: discard-list GET parses into a set and retries-with-backoff until non-empty; POST sends the required params (`commanderName`, `apiKey`, `fromSoftware`, `fromSoftwareVersion`, `fromGameVersion`, `fromGameBuild`, `message=json.dumps(batch)`); `msgnum` classification (1xx OK, 2xx fatal/no-retry, 5xx transient/retry); rate-limit header backoff (remaining 0 → wait until reset); per-event result array handled defensively
- [x] 2.2 Implement a stdlib `urllib` EDSM client (discard GET + journal POST) reusing the shared SSL context, until 2.1 passes

## 3. EDSM consumer (backend, TDD)

- [x] 3.1 Write `tests/test_edsm_consumer.py` covering: `observe` queues non-discarded events verbatim and drops discarded ones; nothing queued when no API key; nothing forwarded on Legacy game version; flush on size threshold and on time threshold; forced flush on `on_session_stop`; transient-state hints added from `SessionState` when present; events kept in journal order; EDSM failure leaves EDDN untouched
- [x] 3.2 Write per-EDSM stats tests: success/fail counts + last `msgnum`/`msg` exposed via `get_stats()` under the consumer `name`; reset on `on_session_start`; fatal `msgnum` (201/202/203/205/208) surfaced and not retried; 5xx retained for retry; discard-fetch failure fails safe (no forwarding, condition surfaced)
- [x] 3.3 Implement `src/modules/forwarders/edsm.py` (`StreamConsumer`: discard filter, ordered buffer + size/time flush, `on_session_start`/`on_session_stop`, `name`/`get_stats`, msgnum + rate-limit handling) until 3.1–3.2 pass

## 4. Credentials & settings (backend, TDD)

- [x] 4.1 Write tests for new settings (EDSM commander name + API key) and the backend callables to get/set them; EDSM inactive (no fetch, no queue) when API key absent
- [x] 4.2 Add EDSM settings keys and `set_edsm_credentials` (and getter as needed) callables in `main.py`/settings until 4.1 passes

## 5. Per-target stats aggregation (backend, TDD)

- [x] 5.1 Write tests asserting `get_status` and the `status_update` emit return a **target-keyed map** built by iterating consumers (no hardcoded `eddn`/`edsm` keys); EDDN counts isolated from EDSM counts; `set_ed_running(true)` resets every target's counts to zero and emits the zeroed map; existing EDDN message output/tests remain green (no regression)
- [x] 5.2 Refactor stats reporting in `main.py` to aggregate per-target by iterating the consumer registry; wire EDDN's existing counters in as one target entry; ensure reset covers all consumers, until 5.1 passes

## 6. Wiring (backend, TDD)

- [x] 6.1 Write a test that `main.py` registers the EDSM consumer in the watcher's consumer list (alongside the session accumulator) and that `on_session_start`/`on_session_stop` reach it
- [x] 6.2 Instantiate and register the EDSM consumer in `main.py`; call lifecycle hooks at the `set_ed_running(true)` hook and watcher stop until 6.1 passes

## 7. Frontend

- [x] 7.1 Change the stats type in `src/types.d.ts` to a target-keyed map (`Record<string, {success, fail}>`) and update the `status_update` payload type; add EDSM credential + EDSM status types; add `getEdsmCredentials`/`setEdsmCredentials` (as needed) to `src/api.ts`
- [x] 7.2 In `src/Content.tsx`, render upload stats by **mapping over** the per-target entries (no hardcoded blocks); add a compact EDSM status block (counts + last message)
- [x] 7.3 In `src/Content.tsx`, add EDSM credential inputs (commander name + API key) mirroring the uploader-ID field, with a link to the EDSM API-key page and an identifiability/consent notice; show an "inactive — API key required" state when unset

## 8. Verification + docs

- [x] 8.1 Run the full test suite + lint/typecheck + frontend build — all green; confirm existing EDDN tests are unchanged (no regression)
- [x] 8.2 Update `AGENTS.md` (new `forwarders/edsm` module, shared `ssl_context`, new callables + settings, per-target stats), `README.md` (EDSM feature + how to get/enter an API key + identifiability note), and add a `[Unreleased]` `CHANGELOG.md` entry
- [x] 8.3 Document a manual on-device verification step: enter EDSM credentials, launch ED, confirm events appear on the EDSM profile, EDSM status updates, and EDDN is unaffected when EDSM credentials are wrong (203 surfaced, EDDN keeps working) — see `reports/edsm-manual-verification.md`
