## Context

The plugin is a single-destination EDDN submitter. `watcher._process_file` parses every journal line, then routes only EDDN-reportable events through `validator` transforms to `submitter` (EDDN message format). EDSM does **not** consume EDDN messages — its `api-journal-v1` endpoint ingests **raw journal lines verbatim** under a named account. So EDSM taps the stream *earlier*, at `ParsedEvent.raw`, before EDDN transformation.

The `session-dashboard` change introduces a **stream-consumer fan-out** at exactly that seam: `watcher._process_file` feeds each parsed event to a `list[StreamConsumer]` (protocol: `observe(event, session_state)`) before the `is_reportable` filter. session-dashboard deliberately built **only** the observe fan-out; lifecycle and stats fan-out were left for "the second real case" — which is this change.

Two research docs ground this: `docs/exploration/2026-06-25-multi-target-eddn.md` (architecture + locked decisions D/scope-1 + additive conditions) and `docs/exploration/2026-06-27-edsm-api-surface.md` (EDSM API spike). Backend is stdlib-only (hand-rolled `urllib`).

## Goals / Non-Goals

**Goals:**
- Forward raw journal events to EDSM under the user's own credentials, independent of and isolated from EDDN.
- Make the second target additive: a `StreamConsumer`-based EDSM forwarder slotting into the existing fan-out, with per-target stats aggregated by **iterating the registry** so a 3rd target needs no reshape.
- Identifiable-upload consent handled cleanly (API-key presence as the gate).

**Non-Goals:**
- Inara (needs a per-event transform layer into Inara's schema — its own change).
- A generic credential store or config-driven N-target framework (scope 1: EDSM-only, built so a 3rd is *possible*).
- Per-batch EDSM activity rows in the activity log (EDSM gets a compact status block; EDDN keeps the per-event log).
- Porting EDMC's shopping-event coalescing heuristics, synthesized `Materials`, or `Backpack.json` reads.
- Refactoring EDDN into a consumer — it stays embedded in the watcher (its aux-file reads + batching make extraction a separate, riskier change).

## Decisions

### Decision: Extend the StreamConsumer protocol with lifecycle + stats
Add to the protocol (beyond `observe`): `name: str`, `get_stats() -> dict`, `on_session_start()`, `on_session_stop()`. `main.py` calls `on_session_start()` for every consumer at the `set_ed_running(true)` hook (alongside the existing reset) and `on_session_stop()` at watcher stop. The session-dashboard accumulator gains no-op/zero implementations as needed.

*Why over alternatives:* This is the deferred fan-out session-dashboard scoped out. EDSM is the first consumer that genuinely needs lifecycle (flush on stop, reset per session) and stats (per-target counters), so the protocol generalizes here where the second case forces its shape — not speculatively earlier.

### Decision: Iteration-driven per-target stats (decision "D")
Per-target counters, not a flat total. `main.py` aggregates by **iterating consumers**: `{c.name: c.get_stats() for c in consumers if reports_stats}` plus EDDN's existing counters as one entry. The `status_update` payload and `get_status` return a target-keyed map; the frontend types it as `Record<string, {success, fail}>` and **renders by mapping over entries** — never hardcoded `eddn`/`edsm` keys. Activity granularity is split: EDDN keeps its per-event activity log; EDSM exposes a compact status block (success/fail + last `msgnum`/`msg`).

*Why over alternatives:* A flat combined counter (option C) hides which target is failing — the brief's Q4 failure-isolation concern. Parallel duplicated surfaces (option B) don't scale to a 3rd target. Iteration-driven is the only model where the 3rd target is purely additive (the additive conditions in the brief). EDSM activity is per-*batch*, not per-event, so forcing it into the per-event log would misrepresent it; a compact status block fits its granularity and defers per-batch rows as YAGNI.

### Decision: Discard-list filter, fetched once at consumer start
On `on_session_start` (or first run), `GET https://www.edsm.net/api-journal-v1/discard` into a `frozenset[str]`; retry with backoff until non-empty; do not refresh mid-session (mirrors EDMC). The EDSM consumer forwards an event only if its `event` name is **not** in the set. This is a filter **distinct** from EDDN's `is_reportable` — EDSM wants a much wider event set (whatever isn't discarded). Match `event` strings exactly (case-sensitive). If the discard fetch never succeeds, fail safe by **not** forwarding (avoid spamming rejects) and surface the condition.

*Why over alternatives:* Hardcoding an allow-list would drift from EDSM's server-side rules (also enforced via msgnum 304). Fetch-once matches EDMC and avoids per-event network cost.

### Decision: Simple size+time batch/flush with forced flush on stop
EDSM accepts a single event or a JSON array. Accumulate events in an in-memory ordered buffer; flush when the buffer reaches N events or T seconds elapse, and **force a flush on `on_session_stop`** (and on `Fileheader`/game-version change, to avoid mixing Live/Legacy or sessions). POST is form-encoded: `commanderName`, `apiKey`, `fromSoftware`, `fromSoftwareVersion`, `fromGameVersion`, `fromGameBuild`, `message=json.dumps(batch)`. Enrich with transient-state hints (`_systemName`, `_systemCoordinates`, `_stationName`, `_shipId`) from `SessionState` where available. Live-only — gate on `game_version` (Legacy → don't send; server rejects with 208 anyway).

*Why over EDMC's event-driven `should_send()`:* EDMC's heuristics exist to coalesce in-station shopping events we don't even forward in v1. A size/time flush with a guaranteed shutdown flush is simpler, adequate, and safe because EDSM dedupes server-side (msgnum 101/102/103) — so at-least-once / resend-on-crash can't corrupt state. Keep events in journal order.

### Decision: msgnum + rate-limit response handling
Parse the JSON body's top-level `msgnum` (and per-event array for batches). Classify by hundreds digit: **1xx** = OK; **2xx** = fatal (bad creds 203, blacklisted 205, Legacy 208) → stop retrying, surface a clear user-facing error, record as failure; **5xx** = transient → retry with backoff, keep events for resend. Honor `X-Rate-Limit-Remaining`/`X-Rate-Limit-Reset`: when remaining is 0, wait until reset before retrying. Reuse the SSL-context cascade.

### Decision: Credentials as settings + API-key-presence consent gate
Two new settings: EDSM commander name + API key, entered via a frontend input mirroring the existing uploader-ID field, with a link to `https://www.edsm.net/en/settings/api`. EDSM is **off unless an API key is present** — the key's presence *is* the opt-in, paired with a one-line notice that flight logs upload under the user's named EDSM identity (vs EDDN's anonymity). No separate validate endpoint exists; validate by submitting and surfacing 201/202/203 as "check credentials". Store the key as a sensitive settings value.

### Decision: Lift `_build_ssl_context()` into a shared helper
Move it out of `submitter.py` into a shared module (e.g. `src/modules/ssl_context.py`) and import it from both EDDN and EDSM. EDDN behavior byte-for-byte unchanged — same function, new home.

## Risks / Trade-offs

- **EDDN regression from shared touch points** (stats aggregation, SSL helper move) → Keep EDDN's submit/validate/transform paths untouched; only the *reporting* aggregation changes. Existing EDDN tests must stay green; assert byte-for-byte message output unchanged.
- **UNVERIFIED rate-limit quota / max batch size** (not in EDSM docs) → Keep batches modest, flush on shutdown, honor the rate-limit headers at runtime; treat unknowns conservatively.
- **UNVERIFIED `fromSoftware` blacklist risk (msgnum 205)** → Use a clear, identifiable `fromSoftware` string; handle 205 as a fatal, user-surfaced error rather than silent failure. Consider notifying EDSM of the software name.
- **UNVERIFIED per-event batch response shape** → Confirm against a real authenticated response during build; defensively treat any non-1xx per-event status as a warning.
- **Discard-fetch failure leaves EDSM idle** → Fail safe (don't forward), surface status; retry with backoff. EDDN unaffected.
- **Dependency on session-dashboard seam** → This change assumes the `StreamConsumer` fan-out exists. session-dashboard should land first; if sequencing slips, this change would also build the observe fan-out.
- **Credentials are linear per target** (accepted) → one settings pair + one input per network target; not generalized into a credential store (would be speculative for a second target).

## Open Questions

- Default flush thresholds (N events / T seconds) — pick conservative starting values, tune on-device.
- Whether to do a lightweight credential pre-check (commander-v1 GET) on save, or validate purely on first submit.
- Re-verify the live EDSM docs in a browser (Cloudflare blocked automated fetch) before finalizing the per-event response handling.
