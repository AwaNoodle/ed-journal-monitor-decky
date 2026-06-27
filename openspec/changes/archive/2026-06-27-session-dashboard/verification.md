# Manual On-Device Verification — Session Dashboard

Automated tests cover the accumulator, watcher fan-out, lifecycle reset, and the
emit/callable contract. The following must be confirmed manually on the Steam
Deck (the journal stream and Decky emit/poll round-trip can't be exercised in CI).

## Setup

1. `npm run package` and deploy per AGENTS.md:
   - `scp ed-journal-monitor.zip deck@<deck-host>:~/Documents/`
   - Decky Developer mode → Browse → select the zip.
2. Open the plugin panel from the Steam quick-access menu.

## Checks

1. **Empty state** — With ED not running (or no events yet this launch), the
   **Session** section appears first (above Status) and shows the neutral
   "No session activity yet" empty state rather than stale numbers.
2. **Live updates** — Launch Elite Dangerous and play:
   - After a hyperspace jump, the hero **Location** line updates to the new
     system and **Jumps** / **Distance (ly)** increment.
   - Scanning bodies increments **Bodies Scanned**; scanning an undiscovered
     body also increments **First Discoveries**.
   - Values update without reopening the panel (live `session_update` emit).
3. **Rehydrate on reopen** — Close and reopen the panel mid-session; the Session
   section immediately shows the current totals (via `get_session_stats`),
   not zeros.
4. **Reset on relaunch** — Quit ED and relaunch it; the Session counters reset to
   zero, then repopulate with the new launch's events (retroactive totals from
   the initial-scan replay, settled into a single update without flicker).
5. **No EDDN regression** — Confirm the Status section's upload counts (✅/❌)
   still advance normally — session stats observe in parallel, they do not gate
   EDDN submission.
