## Why

`codexentry-README.md`'s "BodyID and BodyName" section is normative and specific: the message's `BodyName` may only come from `Status.json`, and `BodyID` only when that value matches the body tracked from `ApproachBody`/`Location` journal events. The plugin does neither — it has no `Status.json` reader and no body tracking at all, and `transform_codex_entry()` forwards whatever `BodyID`/`BodyName` the journal event happened to carry (issue #39).

Both keys are schema-legal, so the gateway accepts the message and nothing surfaces in the plugin's activity log: this is a silent data-quality deviation. The concrete failure the requirement exists to prevent is binary bodies (the README's own example, `Baliscii 7 a` vs `Baliscii 7 b`) — approach one, drop below orbital cruise, turn to the other without a fresh `ApproachBody`, and the journal-tracked body ID no longer describes where the codex entry was logged.

## What Changes

- Add a `Status.json` reader (the plugin does not read that file today) returning the current `BodyName`, with a freshness gate derived from `Status.json`'s own `timestamp`.
- Track `journal_body_name`/`journal_body_id` in `SessionState` from `ApproachBody`, `Location`, and `CarrierJump`; clear on `LeaveBody`, `FSDJump`, and session boundaries — explicitly **not** on `SupercruiseEntry`.
- Gate `transform_codex_entry()`: emit `BodyName` only from the `Status.json` value, and `BodyID` only when the tracked journal body name matches it. Otherwise omit the keys entirely — never `null`, `""`, or a journal-supplied value that has not been cross-checked.
- Read `Status.json` only when a `CodexEntry` is being processed, not on every poll cycle.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `eddn-submission`: adds the mandated `Status.json`/journal body cross-check for codexentry/1, plus the current-body tracking it depends on.

## Impact

- **Backend**: new `src/modules/status_reader.py`; `SessionState` gains `journal_body_name`, `journal_body_id`, `status_body_name`; `JournalParser.parse_line()` gains body tracking; `JournalWatcher._process_dedicated_schema_event()` refreshes the status body name before a `CodexEntry` transform; `transform_codex_entry()` gains the gate.
- **Frontend**: none. No new callable, no new emitted event, no UI.
- **External**: none. No new pip packages, no new network calls — one small local file read per `CodexEntry` (a rare event).
- **Observable effect**: codex entries logged away from a body, or where the body cannot be verified, are submitted **without** `BodyName`/`BodyID` instead of with unverified ones; entries on a body carry the `Status.json`-confirmed name, and a `BodyID` only when the two sources agree.
- **Audit answer to the issue's open question**: upstream EDDN `live` @ `4ad669b` mentions `Status.json` in exactly one place — `codexentry-README.md`, three hits, all inside this section. No other schema the plugin emits has a `Status.json`-derived augmentation, so the plumbing stays codexentry-local and is not generalized.
- **Out of scope**: watching `Status.json` continuously; exposing status/body state in the UI or the diagnostics bundle; any Status.json-driven feature (e.g. low-fuel triggers).
