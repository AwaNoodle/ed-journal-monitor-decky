## Context

The plugin is a one-way relay: the journal watcher fans parsed events to a list of `StreamConsumer`s (session-stats accumulator, EDSM forwarder) in parallel to EDDN routing. All EDSM code today is **write-only** — `forwarders/edsm_client.py` POSTs raw journal lines to `api-journal-v1` under the user's key. There is no read path, no notion of "asking EDSM a question about a system."

This change introduces the first *read* interaction with EDSM and the first feature that surfaces external knowledge back to the player. It deliberately carries the shared read-side foundation (client, cache, arrival trigger, toggle) that three planned sibling features will reuse (system value, next-in-route, nearest scoopable star), so those become cheap follow-ons.

Constraints: Python 3.9+, stdlib only (no pip). Reuse `build_ssl_context()` (`src/modules/ssl_context.py`) and the custom User-Agent — EDSM 403s the default urllib UA behind Cloudflare. EDSM is a free community service, so read traffic must be minimal and cached.

## Goals / Non-Goals

**Goals:**
- A reusable read-side EDSM client for the public `api-system-v1` endpoints, isolated from all submission paths.
- A per-system TTL cache so re-jumping never re-queries.
- An arrival trigger (FSDJump/Location) that fires at most one lookup per system entered, non-blocking.
- A red/yellow/green "worth scanning" verdict, surfaced as an EDSM-attributed chip in the Session dashboard.
- A persisted enable/disable toggle in the EDSM config section, independent of the API key.

**Non-Goals:**
- System estimated-value, priority bodies, next-in-route look-ahead, nearest-anything — future sibling specs.
- Reconciling the verdict against the honk's `BodyCount` (correcting for bodies EDSM doesn't know) — future enhancement.
- Any change to EDDN or EDSM-write behaviour.
- Using the API key for reads (the system endpoints are public).

## Decisions

**Separate read client, not an extension of `edsm_client.py`.**
The write client is a POST/batch/backoff machine coupled to journal forwarding. A new read client (e.g. `forwarders/edsm_read_client.py` or `modules/edsm_lookup_client.py`) keeps read and write concerns cleanly split, sharing only the UA constant and `build_ssl_context()`. Alternative — bolting GET methods onto the existing client — was rejected: it would entangle the consent-gated write path with the public read path.

**Lookup orchestration as a stream consumer vs. a session-state hook.**
The arrival trigger observes FSDJump/Location. The existing `StreamConsumer` protocol already receives `observe(event, session_state)` for every parsed event, so a dedicated consumer (e.g. `EdsmLookupConsumer`) is the natural home: it sees arrivals, dedupes per system via session state, and owns the cache. This keeps it parallel to and non-gating of EDDN/EDSM-write, consistent with the existing architecture. Alternative — wiring into `main.py` arrival handling directly — was rejected as less consistent and harder to test in isolation.

**Verdict is computed backend-side; frontend renders a colour + label.**
The backend emits a small verdict payload (`{system, verdict: "green"|"yellow"|"red"|null, source: "edsm"}`) via a decky event and includes it in `get_status`/session state for rehydrate-on-open. The frontend stays dumb: map verdict → chip colour + EDSM label. Keeps game logic testable in pytest.

**Async, fire-and-forget lookups.**
The lookup runs as an asyncio task off the arrival observation; its result updates cache + emits an event when it lands. Parsing/EDDN/EDSM-write never await it. A failed or slow lookup degrades to the neutral "no verdict" state.

**Toggle is a new settings key, gates at the consumer boundary.**
`edsm_lookups_enabled` (default off, to be conservative with a community API and to make the feature opt-in). When false, the consumer short-circuits before any network call. Independent of `edsm_api_key`.

**Green includes "unknown to EDSM".**
A system EDSM has never heard of is the strongest possible virgin signal, so it maps to green — with the same EDSM-sourced labelling, since absence of data is itself EDSM-sourced inference.

**`isMapped` is not available on `api-system-v1/bodies`.**
Confirmed against live EDSM responses (2026-07-06): the bodies endpoint exposes a `discovery` dict per body (FSS-scanned and submitted) but no `isMapped` or `mapped` field. Red verdict therefore means "all known bodies are FSS-discovered" not "fully mapped". Mapping-aware verdicts would require a different endpoint or a future EDSM API addition.

## Risks / Trade-offs

- **[EDSM completeness makes red/green fallible]** EDSM only knows uploaded bodies; "all discovered" can be wrong if bodies are missing. → Chip is explicitly EDSM-attributed, never presented as ground truth; honk-`BodyCount` reconciliation is noted as a future enhancement.
- **[Load on a free community service]** → Per-system TTL cache, one call per arrival max, feature defaults off, and the toggle. Reuse the existing UA to stay Cloudflare-friendly.
- **[Latency/outage]** EDSM could be slow or down. → Fully async and fire-and-forget; degrades to neutral; never gates submission or parsing.
- **[Verdict semantics ambiguity: discovered vs mapped]** The `bodies` payload's discovery/mapping fields must be read correctly per EDSM's schema. → Pin the exact fields during implementation against a captured sample; cover green/yellow/red and unknown/failure with unit tests over fixtures.
- **[Chip clutter on a small screen]** → Single compact chip in the existing metric area, neutral when absent; no new panel section.

## Open Questions

- Exact `api-system-v1/bodies` field names for discovered/mapped state (and whether "mapped" is reliably present) — confirm against a live/captured response before finalizing the verdict mapping.
- TTL value — hours vs. per-session. Leaning a few hours; a system's explored state changes slowly.
- Cache scope — in-memory only (simplest; lost on restart) vs. persisted. Leaning in-memory for now.
