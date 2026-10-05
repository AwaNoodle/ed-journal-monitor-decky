## Project: ED Journal Monitor Decky Plugin

Decky plugin that watches Elite Dangerous journal files and submits events to EDDN, optionally forwards them to EDSM, and shows EDSM-based navigation aids.

## Stack and constraints
- Frontend: TypeScript + React on `@decky/api` / `@decky/ui`, built with Rollup.
- Backend: Python 3.9+ (CI floor), asyncio, **stdlib only — no pip packages**.
- On-device, Decky's PyInstaller-embedded Python 3.11 cannot find system CA certs. Every outbound HTTPS call must use `ssl_context.build_ssl_context()` (explicit CA cascade: env → certifi → system paths).
- No root flag in `plugin.json`.

## Commands
- Test: `npm run test` (or `PYTHONPATH=. .venv/bin/python -m pytest tests/ -v`)
- Lint/typecheck: `npm run lint:ts` · `npm run lint:py` (ruff + the full pytest suite)
- Package: `npm run package` → `ed-journal-monitor.zip`
- **Never** copy files directly into `/home/deck/homebrew/plugins/` on a device — it breaks Decky developer mode.

## Architecture
- Frontend → backend: `callable()`, declared in `src/api.ts`. Backend → frontend: `decky.emit()`; payload types in `src/types.d.ts`.
- `main.py` wires the backend modules in `src/modules/`. `src/index.tsx` handles game lifecycle (SteamClient app-lifetime and resume-from-suspend notifications, `check_ed_running` at load) and plugin registration. `src/Content.tsx` is the panel.
- The watcher fans every parsed event out to `StreamConsumer`s (`stream_consumer.py`) **before** the EDDN reportable filter; consumers never gate EDDN routing. `main.py` drives `on_session_start()` at `set_ed_running(true)` and `on_session_stop()` when the watcher stops. Route-aware consumers implement the optional `on_nav_route(route)` hook.
- The EDSM lookup and next-hop consumers share one `SystemLookupCache` and one `EdsmReadClient`, both built in `main.py`, so a previewed hop is a cache hit on arrival.
- Upload stats are a per-target map built by iterating consumers with `reports_upload_stats = True`. Never hardcode per-target keys — a new target must be purely additive.
- Activity entries carry a `target` (`UploadTarget` in `constants.py`). EDSM records per event and only on a terminal batch outcome, so EDDN and EDSM counts mean the same unit.

## Invariants

### Journal directory is untrusted input
It is user-settable and may sit on removable media.
- Every limit is a named constant in `constants.py`, never an inline number.
- Before opening any file from it, require a regular file (`stat.S_ISREG`, which follows symlinks) within its size cap — opening a FIFO or device blocks the plugin's single event loop forever. Journals: `watcher._is_usable_journal()`; sidecars: `parser.is_parseable_sidecar()`.
- `_file_positions` are **byte offsets**. Reads are capped chunks (`JOURNAL_READ_CHUNK_BYTES`) in a thread executor; only newline-terminated lines are dispatched. A file smaller than its stored offset is treated as rotated.
- `start()` sets `is_running` only once the initial scan has run and the poll task exists. `_stop_requested` is checked per file **and** per line during the catch-up replay, because the replay awaits real submissions.
- Sidecar readers never raise and return `None` on failure; `status_reader._try_read` catches `Exception` (`RecursionError`/`MemoryError` included).
- `Commander` is stored only when it is a `str` of stripped length 1..`MAX_COMMANDER_NAME_LENGTH` — it becomes the public EDDN `uploaderID`.

### Network
- Every outbound HTTP body read goes through `http_read.read_capped_body()`. An over-sized body is an unusable response — reject it, never truncate. Server-supplied text that reaches the log or frontend is capped at `MAX_SERVER_MESSAGE_CHARS`.
- `edsm_lookups_enabled` (default off) gates every EDSM read call.
- Each EDSM lookup consumer caps in-flight lookups at `MAX_CONCURRENT_EDSM_LOOKUPS`; a new arrival preempts the oldest rather than queueing. `SystemLookupCache` is LRU-bounded by `MAX_SYSTEM_CACHE_ENTRIES`; a hit refreshes recency but never extends the TTL.

### EDSM forwarding and credentials
- The API key's presence is the consent gate for identifiable uploads; EDSM forwarding is off until it is set. `clear_edsm_credentials` deletes the key/name and calls `EdsmForwarder.disarm()`, which stops forwarding mid-session without resetting counters.
- The forwarder sends raw journal lines verbatim (no EDDN transform), enriching a **copy** of the event; it is fully isolated from EDDN.
- Flushes are serialised by one `asyncio.Lock` held across the buffer swap, the rate-limit gate and the send, with the POST in a thread executor. Splitting the lock reorders batches and POSTs through a 429 window.
- `main.py._unload()` must `await self.edsm.drain()` after `_notify_consumers_session_stop()`, or the final batch is lost on a plugin reload.
- `PluginSettings.save()` writes a 0600 temp file, fsyncs and `replace()`s it, and chmods the directory 0700 on every save. `save()`/`delete()` return `bool` and never raise; `delete()` restores the in-memory value when the write fails.
- The API key `TextField` uses `bIsPassword` (the panel appears in screenshots and Remote Play).
- Diagnostics never copy `settings.json` verbatim: redact `SECRET_SETTING_KEYS` (a deny-set, so new settings stay diagnosable) and home-mask paths in `runtime_state.json`. `uploader_id` stays unmasked — it is already public.

### Frontend
- `index.tsx` owns the `edsm_worth_scanning` toast listener (alive for the whole Steam session); `Content.tsx`'s listener ignores `notify`. `main.py._edsm_verdict` must never store `notify`, or a status fetch would replay a toast.
- Collapsed panel sections are not rendered (not CSS-hidden), so they add no gamepad focus stops. `@decky/ui` has no collapsible primitive; `CollapsibleSection` is local. Collapse state is plain `useState` and resets on each panel open by design.

## EDDN/EDSM compliance
- All changes **MUST** follow the [EDDN Developers Guide](https://github.com/EDCD/EDDN/blob/live/docs/Developers.md), and schema handling **MUST** match each schema's README in the [EDDN live schemas folder](https://github.com/EDCD/EDDN/blob/live/schemas). Cross-reference the relevant README before changing any transform, validation, filtering or submission logic.
- **`schema-versions.md`** records what was last checked upstream (pinned commit, per-schema dates, known deviations, EDSM's per-endpoint contract). Read it before such changes; re-run the check with the `checking-schema-updates` skill and update it afterwards. Where a README contradicts the schema JSON, the schema wins.
- **Strict schemas are built by allow-list projection.** Every journal-sourced schema except `journal/1` (and `fcmaterials_journal/1`'s `Items[]`) has `additionalProperties: false`, so `_project_allowed()` (`validator.py`) intersects the payload with `eddn_allowed_fields.ALLOW_LISTS` as the final step. Those two open containers use the blacklist (`_strip_disallowed()`, `EDDN_DISALLOWED_FIELDS`, `JOURNAL_1_ONLY_DISALLOWED`). `tests/test_eddn_allowed_fields.py` re-derives the allow-lists from `tests/fixtures/eddn-schemas/`.
- **`REQUIRED_FIELDS` carries only the target schema's own `required` list, minus keys the transform adds.** A locally-required field that is optional upstream silently drops valid events before transform.
- **`uniqueItems` arrays are deduped before submit** via `_dedupe_preserving_order()`: outfitting/2 `modules`, shipyard/2 `ships`, commodity/3 `statusFlags`. A duplicate is not rejected — the gateway returns 200 and records a warning visible only on the EDDN monitor. The helper is `str`-only and caps at `MAX_UNIQUE_ARRAY_ITEMS`. commodity/3 has `minItems: 1` on `statusFlags`, so omit the key when empty rather than sending `[]`.
- **`horizons`/`odyssey` are tri-state.** `SessionState` holds `None` until `LoadGame` actually carries the key; transforms write them only when not `None`, via `_set_horizons_odyssey()`. Never send a guessed value.
- **Header:** always set `gameversion`/`gamebuild` (`""` when unknown); never set `gatewayTimestamp`.
- **Retry:** first retry no sooner than 60 s (`INITIAL_RETRY_DELAY`), exponential to `MAX_RETRY_DELAY` with jitter.
- **outfitting/2** drops modules whose name case-insensitively equals `int_planetapproachsuite` (the `_advanced` variant is kept).
- **commodity/3** sends `stationType` when present and `carrierDockingAccess` only when truthy (omitted, never empty). The README's "remove `StationType`" line is stale versus the schema. Its "skip `categoryname: NonMarketable`" instruction applies only to CAPI data, not `Market.json` — do not add a category filter; only `StockBracket == 0 and DemandBracket == 0` gates inclusion.
- **codexentry/1 `BodyName`/`BodyID`:** never forward the journal's values. `BodyName` comes only from `Status.json` (read on demand for `CodexEntry`), trusted only within `STATUS_BODY_MAX_SKEW_SECONDS` of the event; `BodyID` is added only when that name equals `SessionState.journal_body_name`. Any doubt → omit the key (never `null`/`""`).

## Coding rules
- Write tests before or alongside every change, and make sure the change has a verifiable success check.
- Run `npm run lint:ts` and `npm run lint:py` before committing or marking work complete; all tests must pass.
- Update `README.md` when user-facing behaviour, features or supported events change.
- Add a `CHANGELOG.md` entry under `[Unreleased]` for changes users can notice: 1–2 sentences on what changed and, if not obvious, why. These become the GitHub Release notes, so no internal mechanics (module names, payload fields, callables, caching/threading, rejected alternatives).
- **No changelog entry for changes users can't observe:** CI/workflow, dev-dependency and toolchain bumps, tests, behaviour-neutral refactors, docs, housekeeping. Exception: when such a change fixes something a user could see (e.g. a release shipping the wrong artifact), write the entry for that consequence.
- Releases: follow the `releasing` skill exactly; do not improvise.
- `npm run package` must keep excluding `__pycache__`/`.pyc` from the zip (enforced by `scripts/verify-package-contents.sh`).
- CI guard logic lives in `scripts/*.sh` with matching `tests/test_*.py` — change it there, not inline in workflow YAML.
- Maintaining this file: record only conventions and non-obvious invariants an agent would otherwise violate. Never add counts, enumerations the code already provides (callables, events, modules, files), descriptions of what code does, or the history of how a rule came about — those belong in the code, the PR, or the OpenSpec archive. Remove entries that stop being true.

## Feature workflow
- All work happens on a dedicated branch or git worktree; `main` takes changes only via Pull Request, never direct pushes.
- Merge PRs with squash and rebase so `main` keeps a linear history.

## Reporting
- All report and review output (code reviews, diagnostics, analysis, etc.) goes in `./reports/`.
