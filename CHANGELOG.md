# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Station outfitting uploads no longer include the Int_PlanetApproachSuite module, which EDDN's schema requires omitting.
- The Horizons/Odyssey flags on uploaded events now reflect only what the game has actually reported, instead of assuming both are owned before that's been confirmed.

### Changed

- Failed EDDN uploads now wait at least a minute before retrying (previously as little as 5 seconds), in line with EDDN's guidance.

## [0.8.2] - 2026-08-28

### Fixed

- Release downloads no longer include leftover compiled Python files, roughly halving the plugin's download size.

## [0.8.1] - 2026-08-28

### Fixed

- Station outfitting uploads no longer contain duplicate module entries, which EDDN was accepting but flagging as warnings. Elite lists some modules twice when they can be bought with either credits or Powerplay merc coins.

### Changed

- Release packaging checks are now covered by automated tests, so a weakened check can't silently slip through.
- Rewrote the README around what the plugin does for you and how to get started, moving EDDN schema reference into the developer guide and adding contributor setup instructions.

## [0.8.0] - 2026-08-12

### Changed

- **Reorganised the panel by how often you actually look at each part**: a health strip, Navigation, and Session are now always visible at the top, while Data flow, Setup, and Troubleshooting collapse behind expandable headers that summarise their state — cutting the number of gamepad D-pad stops needed to reach in-flight information. The Next hop preview is now always shown, including stating plainly when the destination has been reached. The **Find Nearest Scoopable Star** button now turns EDSM lookups on for you if they're off, instead of just telling you to enable them.

## [0.7.0] - 2026-07-28

### Added

- **Worth-scanning arrival notifications**: a Steam toast on arrival in a system worth scanning, so you see it over the running game without opening the quick access menu. Off by default; two new EDSM toggles enable it and set the threshold (green-only, or green + yellow). Tapping the toast opens the plugin panel.
- **Nearest scoopable star lookup**: a **Find Nearest Scoopable Star** button in the Session dashboard reports the closest system with a fuel-scoopable star within 25 ly, for when you're low on fuel. On-demand rather than per-jump to keep EDSM traffic minimal; uses the existing **Enable EDSM lookup** toggle.

### Fixed

- CI lint failure after ruff 0.16 enabled `PLR0917` by default; ignored alongside the equivalent `PLR0913`.
- Duplicate CI runs on every PR push — the Build workflow's `push` trigger is now scoped to `main`, leaving PR coverage to `pull_request`.

## [0.6.0] - 2026-07-14

### Added

- **EDSM worth-scanning lookup**: on arrival in a system (`FSDJump`/`Location`), the plugin can now fetch EDSM's public system body data and display a glanceable **worth-scanning chip** in the Session dashboard — green (unknown/unexplored), yellow (partially explored), or red (fully explored per EDSM). The chip is labelled as EDSM-sourced and updates live on each arrival. A new **Enable EDSM lookup** toggle in the Status section controls this feature; it is **off by default** and independent of the EDSM API key (the system endpoints are public and require no key). Lookups are fully isolated from EDDN and EDSM-write: a read failure or EDSM outage never affects submission. Results are cached per-system (4 h TTL) so re-jumping to a known system makes no new request. New `set_edsm_lookups_enabled` callable and `edsm_lookups_enabled` setting.
- **EDSM system value lookup**: the same arrival lookup now also fetches EDSM's `estimated-value` endpoint and derives a system value summary — total estimated scan value plus a ranked top-3 list of priority (highest-value) bodies. Displayed next to the worth-scanning chip in the Session dashboard, labelled as an EDSM-sourced estimate/floor (it excludes any first-mapped bonus). Reuses the same read client, per-system cache, arrival trigger, and **Enable EDSM lookup** toggle as the worth-scanning chip — no new setting. A value-fetch failure is contained independently of the worth-scanning verdict and reports a neutral (absent) display rather than a stale or misleading figure.
- **EDSM next-in-route hop preview**: when a route is plotted, the Session dashboard now shows a **Next hop** preview for the next system in the route before you jump — its name, primary-star **scoopability** (fuel safety, from the route's own star class), and its EDSM worth-scanning verdict and value when available. The next hop is derived from the already-parsed `NavRoute.json` (matched to the current system by SystemAddress, then name) and advances after each jump; re-plotting updates it live. Reuses the same read client, per-system cache, and **Enable EDSM lookup** toggle as the worth-scanning chip (the previewed system is usually a cache hit once you jump into it) — no new setting. Non-blocking and contained: an EDSM read failure leaves the scoopability signal intact (verdict/value simply go neutral) and never affects submission. New `edsm_next_hop` event and `edsm_next_hop` field on `get_status`.

### Fixed

- **Re-enable EDSM lookups now fires an immediate lookup**: previously, toggling EDSM lookups back on only cleared the dedup state so the verdict would refresh on the _next_ jump, leaving the chip empty if the player never jumped. `set_edsm_lookups_enabled(True)` now calls `force_lookup` with the current system, so the chip populates immediately.
- **`edsm_worth_scanning` module docstring now accessible**: the docstring was placed after `from __future__ import annotations`, making `__doc__` return `None`. Moved to the top of the file per PEP 257.
- **EDSM lookup staleness guard**: if the player jumps to a new system while a previous lookup is still in flight, the stale result is now silently discarded instead of overwriting the current system's verdict.
- **EDSM unavailable result not cached**: `STATUS_UNAVAILABLE` results (network error / timeout) are no longer written to the per-session cache, so the next arrival in the same system retries the lookup rather than sticking on a transient failure.
- **Stale worth-scanning chip after ED quits**: `set_ed_running(False)` now clears `_edsm_verdict` and emits an `edsm_worth_scanning` clear event so the chip disappears when the game exits.
- **Chip persists after EDSM lookup toggle-off**: `set_edsm_lookups_enabled(False)` now clears `_edsm_verdict` and emits a null clear event; the frontend `handleEdsmLookupsToggle` also calls `setEdsmWorthScanning(null)` immediately. The `worthScanningListener` now treats `{verdict: null}` as a clear signal rather than passing it through to the chip renderer.

### Internal

- The Release workflow now triggers on tag push (`v*`): pushing a tag lints, tests, packages, creates the GitHub Release with notes from the matching `CHANGELOG.md` section, and attaches the built `.zip`. Previously the GitHub Release had to be created by hand. The manually-published-Release path is still supported.
- Module docstrings in `edsm_lookup_consumer.py`, `edsm_read_client.py`, `edsm_system_cache.py`, and `edsm_worth_scanning.py` moved to before `from __future__ import annotations` (PEP 257 / Python convention).
- `EDSM_USER_AGENT` centralised in `constants.py`; both EDSM clients (`edsm_read_client.py` and `forwarders/edsm_client.py`) now import it instead of each defining an independent copy.
- `EdsmLookupConsumer.clear_last_system()` replaced by `force_lookup(system_name)`, which bypasses dedup and immediately fires a background lookup — a cleaner API that both resets state and populates the chip without waiting for the next jump.

## [0.5.0] - 2026-07-01

### Added

- **EDSM forwarding**: a second submission target that forwards your raw journal events to your [EDSM](https://www.edsm.net/) profile, alongside (and isolated from) EDDN. Enter your EDSM commander name and API key in the new **EDSM** panel section to enable it — uploads are **off by default** because EDSM submissions are identifiable (tied to your named account), unlike anonymous EDDN. Includes EDSM's discard-list filter, batched submission with size/time/shutdown flush, and `msgnum`/rate-limit handling. The EDSM section shows a live status line (inactive / enabled / active), confirms when credentials are saved, and lets you update the commander name without re-pasting the key; EDSM failures surface per-event in Recent Errors. Saving credentials while Elite Dangerous is already running activates EDSM immediately (no relaunch needed). New `set_edsm_credentials`/`get_edsm_credentials` callables and `edsm_commander_name`/`edsm_api_key` settings.
- **Target-tagged activity log**: Recent Activity and Recent Errors now show which target (EDDN / EDSM) each event was sent to, with a compact target badge on every row. EDSM events are recorded per-event when a batch is confirmed, and EDSM failures (e.g. a bad-key `203`) surface in Recent Errors. Because EDDN (a narrow allow-list) and EDSM (a broad deny-list) carry different, only-partially-overlapping streams, an event sent to both appears as one EDDN row and one EDSM row.

### Changed

- Upload statistics are now reported **per target** (a target-keyed map aggregated by iterating the consumer registry) so EDDN and EDSM counts are independent and a future target is additive. The frontend renders upload counts by mapping over targets. EDDN validation/transform/submission behavior is unchanged.
- EDSM upload statistics are counted **per event** (not per batch), counted only on terminal responses, so the EDDN and EDSM "Uploads" numbers mean the same unit.

### Internal

- Extended the `StreamConsumer` protocol with lifecycle + stats hooks (`name`, `get_stats`, `on_session_start`, `on_session_stop`); `main.py` drives them across all consumers.
- Lifted the shared SSL-context builder out of `submitter.py` into `src/modules/ssl_context.py`, reused by the EDDN submitter and the new EDSM client.

## [0.4.0] - 2026-06-27

### Added

- **Session dashboard**: a live, player-facing summary of the current ED game launch shown at the top of the panel — current system, jumps, distance travelled (ly), bodies scanned, and first discoveries. Stats accumulate from the journal event stream in parallel to EDDN submission, reset on each game launch (and on commander change), and update live via a new `session_update` backend event with a `get_session_stats` rehydrate callable.

### Internal

- Introduced a `StreamConsumer` fan-out seam in the watcher: every parsed event is delivered to registered consumers before the EDDN reportable filter, with the session-stats accumulator (`src/modules/session_stats.py`) as the first consumer. This is the same raw-event tap a future EDSM forwarder will use, so adding it is purely additive.

## [0.3.0] - 2026-06-25

### Added

- EDDN submission for four new journal-sourced schemas: `ScanBaryCentre` (scanbarycentre/1), `FSSBodySignals` (fssbodysignals/1), `DockingGranted` (dockinggranted/1), and `DockingDenied` (dockingdenied/1). Journal-sourced EDDN coverage is now complete (16/16 applicable schemas).

### Documentation

- README EDDN coverage tables reconciled with code: added the previously-undocumented `FCMaterials` (fcmaterials_journal/1) row and the four new schema rows
- Documented that black-market data is not submittable from a journal-only source: `blackmarket/1` is deprecated and the `commodity/3` `prohibited`/`economies` arrays are CAPI-only (the commodity schema forbids sending them from journal `Market.json`)

## [0.2.2] - 2026-06-23

### Changed

- Removed the **Last Upload** row from the status panel — upload events are already visible in the Recent Activity section
- Journal Status active state simplified from "🟢 Watching & Uploading" to "🟢 Watching"

## [0.2.1] - 2026-06-22

### Added

- EDDN submission for `FSSAllBodiesFound` events (fssallbodiesfound/1 schema)

### Fixed

- Recent Activity list layout changed from right-biased to left-biased alignment. Event type and timestamp now display on separate lines, flush left, improving readability in the narrow Steam Deck panel.
- Recent Activity section moved to appear immediately after Status (above Configuration), making upload activity visible without scrolling past configuration fields.

## [0.1.0] - 2026-05-16

### Added

- Elite Dangerous journal file monitoring via polling watcher (Steam Deck compatible)
- EDDN submission for 11 schema types: journal events, commodity, outfitting, shipyard, FSS/SAE signals, navroute, FC materials
- Auto-detection of journal path via Steam `libraryfolders.vdf` scan with manual override
- Game lifecycle detection (start/stop/suspend/resume) via SteamClient events
- Per-event validation with disallowed-field stripping and StarPos augmentation
- Retry logic with exponential backoff and jitter for EDDN submission failures
- Activity log (in-memory circular buffer, 50 entries) with success/failure tracking
- Diagnostic bundle generation for troubleshooting
- Detailed logging toggle (DEBUG/INFO) persisted to settings
- SSL context cascade for PyInstaller-embedded Python certificate resolution
- Frontend UI panel with status, configuration, recent errors, recent activity, and diagnostics
