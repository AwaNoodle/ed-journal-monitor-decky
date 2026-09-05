## 1. Branch setup

- [x] 1.1 Work on a dedicated branch/worktree off `main` (`fix/issue-39-codexentry-status-body`); never commit to `main`

## 2. Status.json reader

- [x] 2.1 Write failing tests (`tests/test_status_reader.py`): `BodyName` present and fresh → returned; `BodyName` absent → `None`; `BodyName` empty or non-string → `None`; file missing → `None`; non-dict JSON → `None`; `timestamp` missing → `None`; skew beyond the window in both directions → `None`; skew inside the window → returned; torn read that parses on a later attempt → returned; torn on every attempt → `None`
- [x] 2.2 Add `STATUS_BODY_MAX_SKEW_SECONDS = 60` (and the `Status.json` filename) to `src/modules/constants.py`
- [x] 2.3 Implement `src/modules/status_reader.py`: async read of `<journal_dir>/Status.json`, bounded retry (3 attempts, 0.1 s apart) for torn reads, timestamp-skew gate against the event timestamp, returns `str | None`; every failure mode logs at debug and returns `None`

## 3. Journal body tracking

- [x] 3.1 Write failing parser tests: `ApproachBody` sets name+id; `Location`/`CarrierJump` set name+id; `LeaveBody` clears; `FSDJump` clears; `SupercruiseEntry` does **not** clear; `Fileheader` clears; event without a body key leaves state untouched
- [x] 3.2 Add `journal_body_name: str = ""`, `journal_body_id: int | None = None`, and `status_body_name: str | None = None` to `SessionState`, documenting that `status_body_name` is populated by the watcher rather than by the parser
- [x] 3.3 Implement the tracking in `JournalParser.parse_line()` (read `Body`, falling back to `BodyName`); confirm ordering against the existing `_update_star_pos()` call for `Location`/`FSDJump`/`CarrierJump`

## 4. Transform gate

- [x] 4.1 Write failing validator tests for `transform_codex_entry()`: status set + names match + id known → both keys; status set + names differ → `BodyName` only, no `BodyID` key; status set + no journal id → `BodyName` only; status unset → neither key, **including when the journal event supplied both**; journal-supplied `BodyName` is replaced by the status value; assert absence of the keys (not `null`/`""`)
- [x] 4.2 Implement the gate: drop journal-supplied `BodyName`/`BodyID` from the payload, then re-add per the cross-check, before `_project_allowed()`
- [x] 4.3 Confirm `tests/test_eddn_schema_conformance.py` and `tests/test_eddn_allowed_fields.py` still pass unchanged (both keys are already schema-legal and allow-listed — no allow-list edit is expected; if one seems needed, stop and re-check)

## 5. Watcher wiring

- [x] 5.1 Write failing watcher tests: processing a `CodexEntry` populates `session_state.status_body_name` from the reader before the transform runs; a non-`CodexEntry` dedicated-schema event triggers no `Status.json` read; a replayed/stale codex entry submits without body keys; a reader failure still submits the message
- [x] 5.2 Refresh `status_body_name` in `JournalWatcher._process_dedicated_schema_event()` for `CodexEntry` only, using the watcher's journal directory; keep the transform dispatch table and every other transform signature unchanged

## 6. Verification & docs

- [x] 6.1 Run the full suite and lint: `npm run test`, `npm run lint:py`, `npm run lint:ts` — all green, no skips added
- [x] 6.2 End-to-end check against a real journal directory (or a fixture copy of one): a codex entry with a fresh `Status.json` naming the same body submits both keys; renaming/removing `Status.json` submits neither; a stale `Status.json` submits neither. Record the observed messages in the PR description
- [x] 6.3 Update `AGENTS.md`: `status_reader` in the module list and Key Files, and an EDDN/EDSM-compliance bullet stating the codexentry cross-check rule and the timestamp-skew gate
- [x] 6.4 Update `schema-versions.md`: move the #39 row out of "Known accepted deviations" into a "Fixed since the 2026-09-03 audit" entry describing what is now sent
- [x] 6.5 Add a short `[Unreleased]` `CHANGELOG.md` entry (user-facing wording: codex-entry uploads now identify the body from the game's live status and omit body details when they can't be confirmed). Update `README.md` only if it describes CodexEntry field-level behaviour
- [x] 6.6 Open a PR referencing issue #39 (merge deferred to reviewer/user per implementation instructions - not merged here)
