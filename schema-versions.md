# Schema Versions

Records the state of our conformance against upstream EDDN and EDSM, not the process for
checking it - see the `checking-schema-updates` skill for the procedure that keeps this
file current.

## EDDN

- **Upstream**: `github.com/EDCD/EDDN`, branch `live`.
- **Last audited commit**: `4ad669b` ("Live branch sync (#236)", authored 2026-06-17).
- **Audit performed**: 2026-08-29.
- **What was checked**: all schema JSON files and their READMEs under `schemas/`, plus
  `docs/Developers.md`.
- **Reference sender**: when a schema README and the schema JSON disagree, the schema wins
  (the READMEs say so themselves). [EDMarketConnector](https://github.com/EDCD/EDMarketConnector)'s
  `plugins/eddn.py` (stable branch) is the reference implementation to consult for what a
  conformant sender actually does. Confirmed disagreement as of this audit: `commodity-README.md`
  still says *"You MUST remove `StationType`"*, but `commodity-v3.0.json`'s `message` object now
  names `stationType` as an allowed property (schema wins - it's fine to send).
- **Schema fixtures**: `tests/fixtures/eddn-schemas/` vendors the 16 schema JSON files
  (approachsettlement, codexentry, commodity, dockingdenied, dockinggranted,
  fcmaterials_journal, fssallbodiesfound, fssbodysignals, fssdiscoveryscan,
  fsssignaldiscovered, journal, navbeaconscan, navroute, outfitting, scanbarycentre,
  shipyard), pinned at the commit above. `tests/test_eddn_allowed_fields.py` re-derives
  each strict schema's allow-list from these fixtures and asserts it matches
  `src/modules/eddn_allowed_fields.py`; `tests/test_eddn_schema_conformance.py` validates
  transform output against them directly. Refresh both the fixtures and this file together
  per the `checking-schema-updates` skill - a stale fixture makes the drift test lie.

### Schemas this plugin emits

| Event(s) | Schema | Last upstream change (`git log -1 -- schemas/<file>`) |
|---|---|---|
| Market | commodity/3 | 2026-06-17 `4ad669b` (stationType/carrierDockingAccess added) |
| Outfitting | outfitting/2 | 2022-09-29 `1999f52` |
| Shipyard | shipyard/2 | 2022-09-29 `1999f52` |
| NavRoute | navroute/1 | 2022-09-29 `1999f52` |
| FCMaterials | fcmaterials_journal/1 | 2022-12-10 `90bf38a` |
| FSSSignalDiscovered | fsssignaldiscovered/1 | 2024-10-31 `72905ef` (SpawningPower/OpposingPower) |
| FSSDiscoveryScan | fssdiscoveryscan/1 | 2022-09-29 `1999f52` |
| ApproachSettlement | approachsettlement/1 | 2023-10-23 `c68de54` |
| CodexEntry | codexentry/1 | 2022-09-29 `1999f52` |
| NavBeaconScan | navbeaconscan/1 | 2022-09-29 `1999f52` |
| FSSAllBodiesFound | fssallbodiesfound/1 | 2022-09-29 `1999f52` |
| ScanBaryCentre | scanbarycentre/1 | 2022-09-29 `1999f52` |
| FSSBodySignals | fssbodysignals/1 | 2022-09-29 `1999f52` |
| DockingGranted | dockinggranted/1 | 2024-01-23 `a43ae03` |
| DockingDenied | dockingdenied/1 | 2024-01-23 `a43ae03` |
| (all journal-sourced events not above) | journal/1 | 2022-09-29 `1999f52` |

The 15 schema types above cover all `DEDICATED_SCHEMA_EVENTS` and `AUXILIARY_FILES` entries in
`src/modules/constants.py`, plus `journal/1` for everything else - 16 schema surfaces in total
counting `journal/1`. Re-derive this table's event-to-schema mapping from that file, not from
here, if they ever disagree.

### Known accepted deviations

Each is filed as a GitHub issue; fix or re-accept there, not by editing this row.

| Issue | Deviation |
|---|---|
| #26 | commodity/3: `stationType` and `carrierDockingAccess` not sent (schema allows both; additive gap, not a rejection) |
| #28 | fsssignaldiscovered: batch `timestamp` uses the *last* signal's, not the first's, contra the README/schema |
| #29 | commodity: the `NonMarketable` category filter (`validator.py`) matches a category string pattern (`nonde`) not seen in any real journal category (`$MARKET_category_<name>;`); likely dead code, unverified against a real `Market.json` |

### Fixed since the 2026-08-29 audit

Branch `fix/eddn-compliance-1-4` merged to `main` as #30 (commit `ad7869f`, 2026-08-31), closing
the gaps below - no longer deviations:

- outfitting/2: `Int_PlanetApproachSuite` is now elided per `outfitting-README.md`'s Elisions
  section (base name, case-insensitive; `_advanced` is kept, matching EDMC)
- `horizons`/`odyssey` are now tri-state (`bool | None`) and omitted from the message entirely
  when unknown, instead of defaulting to a guessed `True`
- `gameversion`/`gamebuild` are now always sent, defaulting to `""` when unknown
- sender-set `gatewayTimestamp` is no longer sent (the gateway overwrites it regardless, but the
  plugin no longer populates it)
- retry backoff now starts at 60s (`INITIAL_RETRY_DELAY`), meeting the documented 1-minute
  minimum, with the cap raised to 300s

### Fixed since the 2026-09-03 audit

Branch `issue-27-eddn-allow-list`, closing #27 (allow-list rework; no upstream schema
change involved - `4ad669b` is still current):

- Every strict (`additionalProperties: false`) schema this plugin builds now projects
  onto an allow-list derived from the schema itself (`src/modules/eddn_allowed_fields.py`,
  applied via `_project_allowed()` in `validator.py`), instead of subtracting a
  hand-maintained blacklist of known-bad fields. `journal/1` and
  `fcmaterials_journal/1`'s `Items[]` are unchanged (genuinely open containers).
- Fixed a live defect this surfaced: `transform_codex_entry()` was injecting a
  `StarSystem` key that `codexentry/1`'s message schema does not allow (the schema
  names the field `System`, which real CodexEntry journal events already carry).
  Since `session_state.star_system` is populated for virtually every session,
  this meant essentially every CodexEntry discovery upload was being rejected by
  the EDDN gateway with `400 FAIL: Schema Validation`. The transform now augments
  `System` (not `StarSystem`) from session state when absent.

## EDSM

No versioned upstream to diff against - EDSM's public API has no schema repo, so this section
is a per-endpoint contract: what we assume, and when we last confirmed it live. Update the
"Last verified" column whenever you re-probe an endpoint; don't touch the assumption text unless
the live response actually changed.

| Endpoint | Contract we depend on | Last verified |
|---|---|---|
| `POST api-journal-v1` (forwarder, `forwarders/edsm_client.py`) | `msgnum` hundreds-digit classification: 1xx OK, 2xx fatal/no-retry, 5xx transient/retry | unverified-in-this-pass (needs the user's API key) |
| `GET api-journal-v1/discard` | Public JSON array of event names EDSM refuses; fetched once per session and cached, not re-fetched per event | unverified-in-this-pass (needs the user's API key to reach the forwarder path that uses it) |
| `GET api-system-v1/bodies` | `discovery` dict present on a body once FSS-scanned/submitted; **no `isMapped` field on this endpoint** | 2026-08-29 (confirmed live: `Sol` planet bodies carry no `isMapped` key; stars carry `isScoopable` directly) |
| `GET api-system-v1/estimated-value` | `estimatedValue` is scan-only - a floor that excludes the mapping bonus (`estimatedValueMapped` is a separate, unused field) | 2026-08-29 (confirmed live: `Sol` returned both fields distinctly) |
| `GET api-v1/sphere-systems` | Returns its own `primaryStar.isScoopable` per system, which we use as-is rather than re-deriving from the star-type string | 2026-08-29 (confirmed live: `showPrimaryStar=1` query around `Sol` returned `primaryStar.isScoopable` directly) |
| All of the above | Custom `User-Agent` (`EDSM_USER_AGENT` in `constants.py`) is required - Cloudflare 403s urllib's default UA | 2026-08-29 (all three GETs above succeeded with the custom UA; confirms the requirement is still real, not that the default UA would fail - that wasn't re-tested) |

Endpoint paths confirmed from `src/modules/edsm_read_client.py` (`EDSM_BODIES_URL`,
`EDSM_VALUE_URL`, `EDSM_SPHERE_URL`) and `src/modules/forwarders/edsm_client.py`
(`EDSM_JOURNAL_URL`, `EDSM_DISCARD_URL`).
