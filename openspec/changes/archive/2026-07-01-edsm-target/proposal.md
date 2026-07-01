## Why

The plugin submits journal data to EDDN only. EDMC — the de-facto standard — fans the same data out to EDDN **and** EDSM **and** Inara. EDSM in particular is free, has a tiny public API, and is the natural "where have I been / where are my scans" companion; many commanders care more about their EDSM profile updating than about anonymous EDDN. Single-destination is a real functional gap. EDSM is the cheapest, highest-value second target, and the session-dashboard change is introducing the stream-consumer seam that makes a second consumer additive rather than a rewrite.

## What Changes

- Add **EDSM** as a second submission destination: a stream consumer that taps the raw parsed-event stream (verbatim journal lines, no EDDN transform) and forwards them to EDSM's `api-journal-v1` endpoint under the commander's own credentials.
- Add an EDSM **discard-list** filter (fetched from EDSM at consumer start, cached) so only events EDSM accepts are forwarded — a filter distinct from the existing EDDN `is_reportable` filter.
- Add **batching + flush** lifecycle for EDSM (size/time flush plus a forced flush on session stop), with `msgnum`-based response classification (1xx OK, 2xx fatal/no-retry, 5xx transient/retry) and `X-Rate-Limit-*` backoff.
- Add EDSM **credentials** (commander name + API key) as new settings with a frontend input, and a **consent gate**: EDSM is off by default and cannot submit without a user-entered API key, because submissions are **identifiable** (tied to a named EDSM account), unlike EDDN.
- **Failure isolation:** EDSM errors MUST NOT affect EDDN and vice-versa. Upload stats become **per-target** (decision "D"): per-target success/fail counters reported via an **iteration-driven registry** (each consumer exposes its name + stats), so a third target is purely additive. EDDN keeps its per-event activity log; EDSM surfaces a compact status block (counts + last `msgnum`/`msg`), not per-event rows.
- Extend the stream-consumer protocol (introduced by `session-dashboard`) with **lifecycle + stats** reporting (`on_session_start`/`on_session_stop`, `name`, `get_stats`) — the deferred fan-out that EDSM is the first real case for.
- **Out of scope (deferred):** Inara (needs a per-event transform layer into Inara's schema — a separate change); a generic credential store; per-batch EDSM activity rows; EDMC's shopping-event coalescing heuristics.

## Capabilities

### New Capabilities
- `edsm-submission`: Forwarding raw journal events to EDSM — the consumer + discard-list filter, batch/flush lifecycle, authenticated POST with `msgnum`/rate-limit handling, credentials + consent contract, and per-EDSM stats with per-session reset and failure isolation from EDDN.

### Modified Capabilities
- `eddn-submission`: the "Track and report upload statistics" requirement changes from a flat `{success_count, fail_count}` to a **per-target** map aggregated by iterating the consumer registry (EDDN becomes one target among several). EDDN validation/transform/submission behavior is otherwise unchanged.
- `upload-stats-reset`: resetting upload statistics on ED start covers **all** per-target consumer stats (EDSM included), not only EDDN's.
- `plugin-ui`: the "Display upload statistics" requirement renders **per-target** stats; adds EDSM credential inputs (commander name + API key, linking to EDSM's API-key page), a consent/identifiability notice, and a compact EDSM status block.

## Impact

- **Backend (stdlib-only):** new `src/modules/forwarders/edsm.py` (consumer: discard fetch, batch/flush, urllib POST, msgnum parsing, rate-limit backoff); lift `_build_ssl_context()` out of `submitter.py` into a shared helper for reuse; extend the `StreamConsumer` protocol with `name`/`get_stats`/`on_session_start`/`on_session_stop`; `main.py` registers the EDSM consumer, aggregates per-target stats by iterating consumers, adds EDSM credential callables; new EDSM settings keys.
- **Frontend:** `types.d.ts` stats type becomes a target-keyed map (`Record<string, {success, fail}>`); `Content.tsx` renders stats by mapping over entries (no hardcoded EDDN/EDSM blocks), adds EDSM credential fields + consent notice + EDSM status block; new `api.ts` entries for EDSM credentials.
- **Dependency:** builds on the `session-dashboard` stream-consumer fan-out seam (`watcher._process_file`); that change should land first.
- **Constraints:** EDDN behavior byte-for-byte unchanged; `observe()` seam stays journal-only (no `source_filepath`); stats aggregation/type/render MUST be iteration-driven so a 3rd target needs no reshape.
- **Docs/meta:** `AGENTS.md` (new module, callables, settings), `README.md` (EDSM feature + setup), `CHANGELOG.md` (`[Unreleased]`).
