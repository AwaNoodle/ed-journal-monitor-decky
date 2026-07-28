## Why

The worth-scanning verdict is only visible if the player opens the Decky quick access menu — which is exactly the thing you don't want to do mid-flight, and exactly when the verdict is most actionable. Decky exposes Steam's native toast system (`toaster` from `@decky/api`), which renders over the running game without any menu interaction, so an arrival verdict can reach the player in the cockpit where the decision to honk actually gets made.

## What Changes

- Two new persisted settings: `edsm_notifications_enabled` (master on/off, default off) and `edsm_notify_all_verdicts` (false = notify on `green` only, true = notify on `green` and `yellow`; default false).
- `EdsmLookupConsumer` computes a `notify: bool` on the worth-scanning payload from those settings plus the derived verdict. `red` and neutral verdicts never notify. The decision is made in the backend, where the settings and session lifecycle already live; the frontend does not hold notification policy or state.
- The `edsm_worth_scanning` decky event payload gains a `notify` field. The field is deliberately **excluded** from the `main.py._edsm_verdict` rehydration dict, so a `get_status` refresh can never replay a toast.
- `src/index.tsx` registers an `edsm_worth_scanning` listener inside `definePlugin()` — alive for the whole Steam session, unlike `Content.tsx`, which is mounted only while the panel is open. When `notify` is true it calls `toaster.toast()` with the system name, estimated value, and top priority bodies, and an `onClick` that opens the Decky quick access tab. The listener is disposed in `onDismount()`.
- `Content.tsx` keeps its existing listener and panel rendering unchanged; it ignores the new `notify` field.
- The two new toggles are surfaced in a grouped **EDSM** settings section, disabled/greyed when `edsm_lookups_enabled` is off (no lookups → no verdicts → nothing to notify with).
- README gains a note that Steam's own "notifications while in game" preference and Do Not Disturb can suppress the toast, since that is outside the plugin's control.

Explicitly out of scope, to keep the change single-hearted:

- **No notification dedupe.** The only suppression is the consumer's existing consecutive-system guard (`_last_system`), so a route that revisits a system (A→B→A) toasts for A twice. Known limitation, not an oversight.
- **No sound.** `playSound`/`sound` are left unset; a beep during a combat drop-in is worse than a missed toast.
- **Default toast duration.** No custom `duration` until there is on-device evidence the default is wrong.
- **No next-hop notification.** `edsm_next_hop` stays panel-only. Possible follow-up.
- **No broader UI restructure.** Only the minimum grouping needed to house the new toggles; the wider panel rethink is its own change.

## Capabilities

### New Capabilities
- `worth-scanning-notification`: In-game Steam toast on arrival in a system worth scanning — the enable/verdict-threshold settings, the backend notify decision, the toast content and tap-through, and the platform-level suppression caveat.

### Modified Capabilities
- `edsm-system-lookup`: the `edsm_worth_scanning` emitted payload gains a `notify` field, and the consumer takes on the notify decision alongside the existing verdict derivation.
- `plugin-ui`: EDSM settings are grouped into a section with the two new toggles; the plugin registers a worth-scanning listener at plugin load rather than only while the panel is mounted.

## Impact

- `src/modules/edsm_lookup_consumer.py` — notify computation on the emitted payload.
- `src/modules/settings.py` — two new persisted keys with defaults.
- `main.py` — new `set_edsm_notifications_enabled` / `set_edsm_notify_all_verdicts` callables; `notify` kept out of `_edsm_verdict`; settings surfaced through `get_status`.
- `src/index.tsx` — `toaster` import, plugin-load listener, `onDismount` disposal.
- `src/api.ts`, `src/types.d.ts` — new callables, `notify` on the event payload, new status fields.
- `src/Content.tsx` — grouped EDSM settings section with the two toggles.
- `tests/` — new coverage for the notify decision matrix and settings persistence.
- `README.md`, `CHANGELOG.md`, `AGENTS.md` — user-facing and architectural documentation.
- No new dependencies. No change to EDDN or EDSM write paths. No new network calls.
