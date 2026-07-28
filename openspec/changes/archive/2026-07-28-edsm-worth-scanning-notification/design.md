## Context

The plugin already derives a worth-scanning verdict on arrival (`EdsmLookupConsumer` → `edsm_worth_scanning` decky event) and renders it in the quick access panel. The verdict is therefore only visible if the player opens the panel — the one interaction they least want mid-flight, and precisely when the verdict is most actionable.

Decky exposes Steam's native toast system as `toaster` from `@decky/api` (`toaster.toast(data): { dismiss() }`). It renders through the same overlay path as achievement and friend-online toasts, so it draws over the running game with no quick access interaction. `ToastData` accepts `ReactNode` for `title`/`body`/`subtext`, plus `onClick`, `duration`, and sound controls. `@decky/ui` exposes `Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky)` for a tap-through.

Two constraints shape the design:

1. **`Content.tsx` is mounted only while the panel is open.** Every existing `addEventListener` call lives there (`src/Content.tsx:105-168`). A listener that only runs while the panel is open is useless for a feature whose purpose is to work while it is closed. Only the `definePlugin()` body in `src/index.tsx` runs for the whole Steam session.
2. **Notification policy needs three inputs** — the settings, the verdict, and (in principle) session state. Two of those already live in the backend.

## Goals / Non-Goals

**Goals:**

- Surface a notifying arrival verdict over the running game with no menu interaction.
- Keep notification policy in one place, with no frontend state to synchronise.
- Make it structurally impossible for a panel open or status refresh to replay a notification.
- Leave the panel, the verdict derivation, EDDN submission, and EDSM forwarding untouched.
- Add zero network calls and zero dependencies.

**Non-Goals:**

- Dedupe of repeat notifications for a revisited system.
- Notification sound.
- Custom toast duration.
- Notifications for the next-in-route preview (`edsm_next_hop`).
- The broader panel UI restructure — only the minimum grouping to house the new toggles.

## Decisions

### Decision 1: The backend decides whether to notify; the frontend only renders

The backend computes `notify: bool` from the persisted settings and the derived verdict, and puts it on the `edsm_worth_scanning` payload. `index.tsx` reduces to `if (data.notify) toaster.toast(...)`.

```
   EdsmLookupConsumer
     ├─ reads edsm_notifications_enabled, edsm_notify_all_verdicts
     ├─ verdict → notify: bool
     └─ emit edsm_worth_scanning { system, verdict, source,
                                   totalValue, priorityBodies, notify }
                    │
                    ├──────────────► index.tsx   if (notify) toast()
                    └──────────────► Content.tsx renders as today, ignores notify
```

*Why:* the settings already persist in the backend (`edsm_lookups_enabled` sets the pattern), the verdict is derived there, and the consumer already owns session lifecycle via `on_session_start()`. Putting the decision there means the frontend holds no notification state at all.

*Alternative considered — frontend decides.* `index.tsx` would cache the settings and evaluate the rule itself. Rejected: `index.tsx` and `Content.tsx` are separate mount scopes, so a toggle flipped in the panel would have to propagate to a listener that is not mounted alongside it. That needs either a shared store, a refresh on `status_update`, or a re-fetch on every event — real machinery, all of it to relocate a rule that has no reason to leave the backend. It also moves the logic out of the pytest suite and into the harder-to-test frontend.

*Alternative considered — backend gates the emit entirely.* Emit `edsm_worth_scanning` only when it should notify. Rejected outright: the panel needs the verdict for every arrival, including red ones.

### Decision 2: Two independent settings, not one enum

`edsm_notifications_enabled: bool` (default `false`) and `edsm_notify_all_verdicts: bool` (default `false` = green only).

*Why:* this is what the feature's user asked for, and the master toggle is the control people actually reach for — turning notifications off and back on preserves the threshold choice. `red` and neutral never notify at either threshold, so "yellow only" is unrepresentable, which is correct: yellow-without-green is not a coherent preference.

*Trade-off:* a three-value enum (`off | green | green+yellow`) would make the invalid-ish state `enabled=false, all_verdicts=true` unrepresentable. That state is harmless — it means "off, and when re-enabled, notify on both" — so the extra ergonomics of a separate master toggle wins.

### Decision 3: `notify` is excluded from the rehydration dict

`main.py._edsm_verdict` stores the latest payload so `get_status` can rehydrate the panel. `notify` is stripped before storing.

*Why:* notifications fire only from the event listener, never from a status fetch, so a stale `true` could not replay a toast anyway. Excluding it makes that a structural property rather than an incidental one — a future refactor that routes rehydration through a shared handler cannot accidentally resurrect a toast.

### Decision 4: Listener in `definePlugin()`, not `alwaysRender: true`

Register the notification listener in the `definePlugin()` body and dispose it in `onDismount()`. `Content.tsx` keeps its own separate listener for the panel; decky's emitter supports multiple listeners per event, so both coexist without coordination.

*Alternative considered — `alwaysRender: true`.* The `Plugin` type supports it, and it would keep a single listener. Rejected: it keeps the entire panel component tree and all its state hooks alive for the whole Steam session to solve a problem one listener registration solves.

*Alternative considered — a shared `src/notifications.ts` module.* Cleaner if this grows to several notification types. Deferred: with exactly one event to handle, the module is indirection without payoff. Revisit when next-hop notifications land.

### Decision 5: Toast content and tap-through

Title names the feature, body names the system, subtext carries value and top priority bodies when present. `onClick` calls `Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky)`.

```
  ┌──────────────────────────────────────┐
  │ Worth scanning                        │
  │ Col 285 Sector XY-Z b12-4            │
  │ ~1.2M cr · ELW, 2x WW         [tap]  │
  └──────────────────────────────────────┘
```

*Why:* the point is to decide whether to honk without opening anything, so the toast must carry enough to decide on. Value can legitimately be absent (a value-fetch failure emits neutral value fields while the verdict still stands) — in that case the subtext is omitted rather than rendered with placeholder text.

## Risks / Trade-offs

**[Repeat notifications on a revisited system]** → Accepted, documented. The consumer's `_last_system` guard (`src/modules/edsm_lookup_consumer.py:67`) is a single string, not a set — it suppresses *consecutive* repeats only, so A→B→A notifies twice for A. Explicitly deferred, but called out in the proposal and changelog so it reads as a known limitation rather than a bug on first sighting.

**[Steam suppresses the toast]** → Cannot be mitigated in code. Steam's "notifications while in game" preference and Do Not Disturb both swallow toasts. Mitigation is documentation: a README note, so a user who sees nothing checks their Steam settings before filing an issue.

**[Notification noise on a long route]** → Mitigated by the green-only default. A 30-jump trip through explored space produces few green verdicts; the same trip through virgin space produces many, but there every toast is a true positive. If on-device use shows it is still too noisy, a value threshold is the natural next lever — the payload already carries `totalValue`.

**[Toast arrives during a hostile drop-in]** → Partly mitigated by shipping no sound: a silent corner toast is ignorable in a way a beep is not. Default duration keeps the intrusion short.

**[Two listeners on one event drift apart]** → Low. They consume disjoint parts of the payload (`Content` ignores `notify`; `index` reads only `notify` and the display fields). Contained by the shared type in `src/types.d.ts`.

**[Settings surface keeps growing]** → This is the third EDSM-ish control. The grouped section is a deliberate holding action, not the fix; the wider panel restructure is left as its own change so this one does not grow a second heart.

## Migration Plan

Purely additive. Both settings default to off, so an existing install behaves exactly as before until the user opts in. No data migration, no schema change, no change to EDDN or EDSM write behaviour. Rollback is reverting the change — no persisted state needs cleaning up, and unknown settings keys are harmless if a user downgrades.

## Open Questions

- Is the default toast duration long enough to read the subtext during a supercruise approach? Deliberately deferred to on-device observation rather than guessed at now.
- Should `red` verdicts ever be surfaced as a "don't bother, jump on" signal? Out of scope here; it inverts the feature's premise and deserves its own discussion.
