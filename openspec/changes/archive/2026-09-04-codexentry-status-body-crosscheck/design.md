## Context

Constraints that shape every decision below:

- The watcher **polls** (`_poll_interval`, default 10 s). It is not a real-time journal reader like EDMC, which processes each line as it is written and receives `Status.json` updates through a dashboard callback (`dashboard_entry()` in `plugins/eddn.py`, which sets `this.status_body_name` on every write).
- The watcher also **replays** journal files on start (`_initial_scan()` / `_replay_initial_scan()`): on catch-up it processes every file modified since the persisted last-active timestamp. A replayed `CodexEntry` can be hours or days old, while `Status.json` on disk always describes *now*.
- `Status.json` lives in the journal directory alongside `Journal*.log`, is rewritten by the game many times per second in flight, and is written non-atomically — a read can land mid-write and fail to parse.
- Only `CodexEntry` needs this data. Verified against upstream EDDN `live` @ `4ad669b`: `grep -rn "Status.json" schemas/ docs/` returns three hits, all in `codexentry-README.md`'s "BodyID and BodyName" section.

Reference implementation for comparison: EDMC `stable` — `plugins/eddn.py:1245-1266` (the gate), `plugins/eddn.py:2658-2664` (`status_body_name` from Status.json), `monitor.py:948-1068` (journal body tracking).

## Goals / Non-Goals

**Goals:**
- `BodyName` on a codexentry/1 message comes only from `Status.json`, and only when that value can be trusted to describe the moment the codex entry was logged.
- `BodyID` only when the journal-tracked body name matches the `Status.json` name.
- Neither key present in any other case — not `null`, not `""`, absent.
- Zero cost when no `CodexEntry` occurs.

**Non-Goals:**
- Continuous `Status.json` watching, or any other Status.json-derived state (fuel, flags, coordinates, on-foot state).
- Surfacing body/status state in the panel or the diagnostics bundle.
- Generalizing a "status augmentation" mechanism across schemas — no other schema needs one.

## Decisions

**Read `Status.json` on demand, at `CodexEntry` processing time.** The alternative — reading it every poll cycle and caching the value — costs a file read every 10 s for the whole session and is *no fresher*: either way the value is read up to one poll interval after the journal line was written. Reading it only when a codex entry is in hand keeps the cost proportional to a rare event. The read happens in `JournalWatcher._process_dedicated_schema_event()`, before the transform, so the validator stays free of I/O and every transform keeps the uniform `(event, session_state)` signature that the dispatch table depends on.

**Trust the value only inside a freshness window, judged by `Status.json`'s own `timestamp`.** `Status.json` carries a `timestamp` field; the `CodexEntry` event carries one too. The value is used only when they are within `STATUS_BODY_MAX_SKEW_SECONDS` (60 s) of each other, in either direction. This single rule covers every way the two can drift apart:

- *Normal live operation*: the status file is newer than the event by at most the poll interval plus processing — inside the window, value used.
- *Catch-up replay*: a codex entry from a previous session is compared against today's `Status.json` — skew of hours or days, value rejected, both keys omitted. This is exactly what the README demands: *"If you cannot properly obtain the values for `BodyName` or `BodyID` then you MUST NOT include them."*
- *Stalled poll / resume from suspend*: same rejection, same reason, no extra machinery.

Alternative rejected: a "replaying" flag on the watcher, set during `_initial_scan()`. It only handles the replay case; a resume-from-suspend gap or a long poll stall would still submit a body name describing a completely different location, and it adds watcher state that the timestamp comparison makes unnecessary. A missing or unparseable `timestamp` in `Status.json` is treated as untrustworthy (keys omitted), not as "assume fresh".

**Bounded retry on a torn read.** `Status.json` is rewritten in place, so `json.loads` failures are expected, not exceptional. Up to 3 attempts, 0.1 s apart, mirroring the existing `_read_auxiliary_data()` retry pattern (same intent, much shorter delays because the file is rewritten continuously rather than produced once). Exhausted attempts → no status body name → keys omitted.

**Journal body tracking lives in `SessionState`, set by `JournalParser.parse_line()`.** Two new fields, `journal_body_name: str = ""` and `journal_body_id: int | None = None`, alongside the existing `star_pos`/`system_address`/`star_system` caching, following exactly the README's rules:

| Event | Action | Source of rule |
|---|---|---|
| `ApproachBody` | set name + id | README step 1 |
| `Location` | set name + id (may be a station; not filtered by `BodyType`) | README step 2 |
| `CarrierJump` | set name + id | EDMC `monitor.py` treats `location`/`carrierjump` identically; the plugin already pairs them in `_update_star_pos()` |
| `LeaveBody` | clear both | README step 3 |
| `FSDJump` | clear both | README step 3 |
| `SupercruiseEntry` | **no action** | README step 3's explicit exception — a player can re-descend without a fresh `ApproachBody` |
| `Fileheader` | clear both | session boundary: a new journal file means new session state; prevents a body from one replayed file leaking into the next |

The journal key is `Body`, not `BodyName` — the README names the concept, the game writes `Body` (confirmed by EDMC's `entry['Body']` in `monitor.py`). Read `Body` first, fall back to `BodyName` if a future game version renames it.

Deliberately **not** tracked: EDMC additionally clears body state on `Music: MainMenu`. Unnecessary here, and provably so: a stale journal body can only ever produce a `BodyID` when its name equals the live `Status.json` name, and in that case it is the correct body. The freshness gate plus the name-match requirement make the extra clear redundant.

**`SessionState.status_body_name` is the one externally-populated field.** Every other `SessionState` field is derived from journal lines by the parser; this one is written by the watcher from the status reader immediately before the codex transform, and documented as such in the dataclass. The alternative — an extra transform parameter — would break the uniform transform signature used by `_process_dedicated_schema_event()`'s dispatch table for nine event types.

**The gate drops journal-supplied values unconditionally, then re-adds what the cross-check proves.** `transform_codex_entry()` pops `BodyName`/`BodyID` from the copied payload before applying the rule. This is a deliberate deviation from EDMC, which only fills the keys in when absent (`if 'BodyName' not in entry:` / `if 'BodyID' not in entry:`, guarding against Frontier adding them to the event). The README is normative and unambiguous — the message's `BodyName` *is* the `status_body_name` value, and `BodyID` MUST be absent when the names disagree — and in the binary-body case a journal-supplied `BodyID` is precisely the wrong value the requirement exists to suppress. Keeping it because the game volunteered it would defeat the fix.

## Risks / Trade-offs

- **[Poll-interval freshness]** With a 10 s poll, a codex entry logged during a fast transit between binary companions can be matched against a `Status.json` that already names the companion. Residual and unavoidable without real-time watching; strictly better than today (which sends an unverified journal body *plus* an unverified `BodyID`), and the name-match rule means a disagreement costs only the omission of `BodyID`.
- **[Fewer body fields submitted]** Codex entries during replay/catch-up, or with no `Status.json` present, now go out without `BodyName`/`BodyID`. That is the required behaviour, and the codexentry-README's own "Listeners" section documents all three shapes (neither key / name only / both) as expected.
- **[Status.json missing]** Not observed — it sits in the journal directory the plugin already resolves — but handled: missing, unreadable, non-dict, empty/non-string `BodyName`, or absent `timestamp` all resolve to "no status body name", keys omitted, no error surfaced to the user.
- **[New parser state]** Body tracking runs for every parsed line of four event types; `SessionState` gains three fields. Additive, no behaviour change for any other schema.

## Open Questions

None. The freshness window value (60 s) is a documented constant, tunable if a live capture shows `Status.json` going stale for longer while a player sits still near a body.
