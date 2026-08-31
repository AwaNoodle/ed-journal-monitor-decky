---
name: checking-schema-updates
description: Use when checking for upstream EDDN schema changes, auditing EDDN/EDSM conformance against the live branch and EDSM's public API, or updating schema-versions.md. Runs the actual comparison - clone + diff + field-set dump + example-event diff - not a restatement of the "follow the guidelines" policy in AGENTS.md.
---

# Checking Schema Updates

Procedure for re-running the EDDN/EDSM conformance audit recorded in `schema-versions.md`.
That file is the state (last commit checked, per-schema dates, known deviations, EDSM
per-endpoint contract); this skill is the mechanics for regenerating it.

## Quick reference

| Step | Command |
|---|---|
| Clone `live` | `git clone --depth 50 --branch live https://github.com/EDCD/EDDN.git <tmp>` |
| What changed since last audit | `git log --oneline <recorded-commit>..HEAD -- schemas/` |
| Per-schema last-modified date | `git log -1 --date=short --pretty='%ad %h' -- schemas/<file>` |
| Dump message-level field constraints | `python3 dump_schema_fields.py <clone>/schemas` (below) |
| Capture a fresh pair | `eddn-tail -S outfitting/2` (or the schema in question), `/` to live-filter on the Software column, `e` to export |
| Probe EDSM live | `curl -sA ed-journal-monitor-decky "https://www.edsm.net/api-system-v1/bodies?systemName=Sol"` |
| Record the result | edit `schema-versions.md` |

## Preconditions

- A shallow clone of `EDCD/EDDN` branch `live`. Depth 50 is enough to reach the commit recorded
  in `schema-versions.md`'s "Last audited commit" - go deeper only if `git log <sha>..HEAD` fails
  to find it.
- `schema-versions.md` open alongside, so you're diffing against what it currently claims, not
  what you remember.

## Procedure

### 1. Clone and find what actually changed

```bash
git clone --depth 50 --branch live https://github.com/EDCD/EDDN.git /tmp/eddn-audit
cd /tmp/eddn-audit
git log --oneline <recorded-commit>..HEAD -- schemas/ docs/Developers.md
```

If this is empty, nothing changed since the last audit - the rest of the run is a re-verification
pass, not a diff review. In the 2026-08-29 audit this returned exactly one commit touching one
file (`commodity-v3.0.json`, a `renamed` annotation fix with no new constraint). Read every commit
this turns up; do not assume "one file" means "trivial" without reading it.

If `git log <recorded-commit>..HEAD` errors because the recorded commit isn't in a depth-50
clone, re-clone with more depth or `git fetch --unshallow`.

### 2. Per-schema last-modified dates

Distinguishes "old but never checked by us" from "changed recently and we haven't looked":

```bash
for f in schemas/*-v*.json; do
  echo -n "$f: "; git log -1 --date=short --pretty='%ad %h' -- "$f"
done
```

Cross-reference against the "Schemas this plugin emits" table in `schema-versions.md` - any date
newer than the "Last audited commit" date is new territory since the last pass, even if step 1's
commit range didn't touch that particular file (it will have, since step 1 already scoped to
`schemas/`, but this catches schemas we don't currently emit that might become relevant).

### 3. Dump each schema's field constraints

This is what surfaced the allow-list-vs-blacklist risk (issue #27): our transforms build
strict-schema messages by copying `event.raw` and subtracting known-bad fields, which is inverted
relative to what `additionalProperties: false` schemas actually require.

```python
import json, glob

for path in sorted(glob.glob("schemas/*.json")):
    d = json.load(open(path))
    msg = d.get("properties", {}).get("message")
    if not msg:
        continue
    print(f"{path}: additionalProperties={msg.get('additionalProperties')} "
          f"required={msg.get('required', [])}")
    for pname, pdef in msg.get("properties", {}).items():
        if pdef.get("type") == "array":
            items = pdef.get("items", {})
            if isinstance(items, dict) and "additionalProperties" in items:
                print(f"   items[{pname}].additionalProperties={items.get('additionalProperties')}")
```

Every schema with `message.additionalProperties=False` is a hard allow-list: any field the
transform emits that isn't named in that schema's `properties` gets a `400` at submit time, and
any field FDev adds to the journal that we blindly pass through will eventually trip this. Only
`journal/1` and `blackmarket` currently allow additional properties. `signals`/`Signals`/`Route`/
`commodities`/`economies`/`StationEconomies` array items carry their own nested
`additionalProperties: false` - a pass-through fill of those (e.g. `SignalBatcher.add_signal()`)
is exposed to the same risk one level down.

### 4. Diff a fresh capture of our own message against a reference sender's

Proves a gap rather than merely suspecting one. This is how the `Int_PlanetApproachSuite`
elision gap (issue tracked in `schema-versions.md`'s "in flight" section) was confirmed, not
just theorized from the README text. It needs live EDDN traffic, captured at audit time with the
user's `eddn-tail` TUI (repo `~/sandbox/personal/eddn-tail`, entry point `eddn_tail.py`, also on
`PATH` as `eddn-tail`) - there is no fixture to check out.

**Captures are not checked in.** `example-events/` is gitignored on purpose, alongside the other
local-exploration paths (`docs/`, `context.md`). A frozen capture is point-in-time evidence of
what senders did that day, not a durable statement of what the schema requires, and it would rot
silently while looking authoritative. It also carries another commander's relay-hashed
`uploaderID` and a third party's software fingerprint - not ours to redistribute. Capture fresh
every time this step runs; never resurrect or vendor an old export.

**This step needs a human at the keyboard.** `eddn-tail` is an interactive TUI with no headless
or scripted export mode - run it, watch the stream, export by hand. Reserve step 4 for when you
need to *prove* a suspected gap, not as something to run unattended on every audit pass.

To capture:

```bash
eddn-tail -S outfitting/2        # or whatever schema is in question
```

Then inside the TUI:
- Press `/` to open the live filter and type a regex matching the Software column, e.g.
  `ED Journal Monitor Decky` or `E:D Market Connector` - the CLI has no `--software` flag, so this
  is the only way to isolate a sender. `Uploader` is relay-hashed with a nonce that rotates every
  3 minutes, so filtering on it is not possible.
- Select the message you want (`↑`/`↓`, `Enter` for full detail) and press `e` to export it to
  `eddn_export_<timestamp>.json` in the current directory - this is where the existing capture
  filenames come from.
- `p` pauses the stream if you need a moment to read; `q` quits.

Our own message only appears on the relay when the plugin actually uploads - i.e. when the user
visits a station in-game while the plugin is running. There's no way to force it from outside the
game.

Two different questions call for two different rigor levels:

- **"What fields does a reference sender send that we don't, or vice versa?"** - the common case.
  Any two recent same-schema captures work; they don't need to be the same station or the same
  minute. Grab our own next upload plus any EDMC (or other reference sender) message of the same
  schema off the live stream.
- **"Do our values differ from theirs for the same real station?"** - rarer, and only relevant
  when comparing station-specific data (e.g. do two senders list the same outfitting stock). This
  needs a same-station, same-minute pair, which is opportunistic - it requires another player
  filtering through that exact station in that window. Use `eddn-tail -t <station>` to narrow to
  it, then wait.

Once you have both exports, diff them. The snippet below is written for `outfitting/2`, where
`message.modules` is a flat list of module-name strings (see `transform_outfitting()` in
`src/modules/validator.py`, and `outfitting-v2.0.json`) - adjust the field path for other
schemas' message shapes:

```bash
python3 -c "
import json
ours = json.load(open('example-events/eddn_export_<ours>.json'))
theirs = json.load(open('example-events/eddn_export_<edmc>.json'))
our_mods = set(ours['message']['modules'])
their_mods = set(theirs['message']['modules'])
print('ours only:', our_mods - their_mods)
print('theirs only:', their_mods - our_mods)
print(len(our_mods), 'vs', len(their_mods))
"
```

### 5. Read the README prose, not just the JSON

Several MUSTs exist only in a schema README's "Elisions" or "Augmentations" section and are
invisible from the JSON alone - the JSON's `pattern`/`enum` may still *permit* a value the README
says must never be sent (e.g. `outfitting-README.md`'s `Int_PlanetApproachSuite` elision: the
schema's module-name pattern allows it, the README forbids it). For every schema this plugin
emits, read its `-README.md` in full, not just grep for field names.

### 6. When README and JSON disagree

The schema JSON wins - every README says so in its own preamble. Confirmed live disagreement as
of the 2026-08-29 audit: `commodity-README.md` still says *"You MUST remove `StationType`"*, but
`commodity-v3.0.json`'s `message.properties` now names `stationType` as allowed (added in the
last-audited commit). When you hit a case like this, check
[EDMarketConnector's `plugins/eddn.py`](https://github.com/EDCD/EDMarketConnector) (stable
branch) - it's the reference sender, and shows what a conformant implementation actually does in
practice, not just what the docs permit.

### 7. Re-probe EDSM's public read endpoints

No versioned repo exists for EDSM, so there's nothing to `git log` - the check is a live request
compared against the assumptions recorded in `schema-versions.md`'s EDSM table. All three system
endpoints are public GETs, no credentials needed:

```bash
UA="ed-journal-monitor-decky"   # must match EDSM_USER_AGENT in src/modules/constants.py
curl -sA "$UA" "https://www.edsm.net/api-system-v1/bodies?systemName=Sol" | python3 -m json.tool | head -40
curl -sA "$UA" "https://www.edsm.net/api-system-v1/estimated-value?systemName=Sol" | python3 -m json.tool
curl -sA "$UA" "https://www.edsm.net/api-v1/sphere-systems?systemName=Sol&radius=10&showPrimaryStar=1" | python3 -m json.tool | head -20
```

Check specifically: does `discovery` still appear per-body with no `isMapped` key, is
`estimatedValue` still distinct from `estimatedValueMapped`, does `sphere-systems` still return
`primaryStar.isScoopable` directly. `api-journal-v1` (the forwarder) needs the user's own EDSM API
key and can't be probed this way - mark it `unverified-in-this-pass` in `schema-versions.md`
rather than guessing at its current behaviour.

### 8. Update schema-versions.md and file issues

- Bump "Last audited commit" to the clone's current `HEAD` (with its subject and author date) and
  "Audit performed" to today.
- Update any per-schema dates that changed.
- Update the EDSM table's "Last verified" column only for endpoints you actually re-probed.
- File a GitHub issue for anything found and not fixed in the same session; link it from the
  "Known accepted deviations" table rather than describing the deviation twice.

## Failure modes

| Symptom | Cause |
|---|---|
| `git log <recorded-commit>..HEAD` errors "unknown revision" | Clone depth too shallow to reach the recorded commit - re-clone deeper or `git fetch --unshallow` |
| Field-dump script finds no `message` key for a schema | That schema's structure differs from the message-envelope shape (e.g. `blackmarket`, `journal`) - read it by hand instead of assuming the loop covers every file uniformly |
| No reference-sender message showing up in `eddn-tail` for step 4 | Either the sender isn't currently active on the schema you're watching, or the live filter regex doesn't match the Software column text - widen the filter or wait longer before concluding it's absent. If you give up, note the gap as unconfirmed (suspected from README text) rather than asserting it as a real deviation |
| EDSM probe returns `{}` instead of a list/dict | For `sphere-systems`, this means the queried system isn't known to EDSM (documented behaviour, not a break) - retry with a known system like `Sol` before concluding the contract changed |
| curl gets `403` from EDSM | User-Agent didn't match - EDSM's Cloudflare rejects the default `curl`/`urllib` UA; the `-A "ed-journal-monitor-decky"` flag above is required, not optional |
