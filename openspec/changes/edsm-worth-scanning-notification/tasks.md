## 1. Settings persistence

- [ ] 1.1 Write tests for the two new settings keys: `edsm_notifications_enabled` defaults to `False`, `edsm_notify_all_verdicts` defaults to `False`, both round-trip through save/load
- [ ] 1.2 Add both keys with defaults to `src/modules/settings.py`

## 2. Backend notify decision

- [ ] 2.1 Write tests for the notify decision matrix in `tests/test_edsm_lookup_consumer.py` — the full cross product of {notifications off, on+green-only, on+all} x {green, yellow, red, neutral}, asserting notify is true only for (on, green-only, green), (on, all, green) and (on, all, yellow)
- [ ] 2.2 Write a test that a value-fetch failure still emits a notify decision derived from the verdict, with neutral value fields
- [ ] 2.3 Write a test that computing the notify decision issues no additional EDSM request
- [ ] 2.4 Implement the notify computation in `src/modules/edsm_lookup_consumer.py` and include `notify` on the emitted `edsm_worth_scanning` payload

## 3. Rehydration exclusion

- [ ] 3.1 Write a test that `main.py._edsm_verdict` stores the payload without the `notify` key after `_on_edsm_verdict`
- [ ] 3.2 Write a test that `get_status()`'s `edsm_worth_scanning` field contains no `notify` key
- [ ] 3.3 Strip `notify` before storing in `_on_edsm_verdict` in `main.py`, verifying `_on_edsm_value` still merges `totalValue`/`priorityBodies` correctly onto the stored dict

## 4. Backend callables

- [ ] 4.1 Write tests for `set_edsm_notifications_enabled` and `set_edsm_notify_all_verdicts` persisting their values and being reflected in `get_status`
- [ ] 4.2 Add both callables to `main.py` and expose the current values through `get_status`
- [ ] 4.3 Run the full Python suite and confirm all tests pass

## 5. Frontend plumbing

- [ ] 5.1 Add `notify?: boolean` to the `EdsmWorthScanningEvent` payload type and the new settings fields to the status type in `src/types.d.ts`
- [ ] 5.2 Add `setEdsmNotificationsEnabled` and `setEdsmNotifyAllVerdicts` to `src/api.ts`

## 6. Toast notification

- [ ] 6.1 In `src/index.tsx`, register an `edsm_worth_scanning` listener inside `definePlugin()` that calls `toaster.toast()` when `notify` is true, with title, system name as body, and value plus top priority bodies as subtext
- [ ] 6.2 Omit the subtext entirely when the payload carries neutral value fields, rather than rendering placeholder text
- [ ] 6.3 Set `onClick` to `Navigation.OpenQuickAccessMenu(QuickAccessTab.Decky)`; set no `sound`/`playSound` and no custom `duration`
- [ ] 6.4 Remove the listener in `onDismount()` alongside the existing SteamClient unregistrations

## 7. Settings UI

- [ ] 7.1 Group the existing EDSM credentials and auto-lookup toggle with the two new controls under a single labelled EDSM section in `src/Content.tsx`
- [ ] 7.2 Add the notifications on/off toggle and the green-only vs all-verdicts control, both reflecting persisted state and calling the new API methods on change
- [ ] 7.3 Render both new controls in a visibly inactive state when `edsm_lookups_enabled` is off
- [ ] 7.4 Confirm the existing panel worth-scanning rendering is unchanged and ignores `notify`
- [ ] 7.5 Run lint and typecheck and confirm both pass

## 8. Documentation

- [ ] 8.1 Update `README.md` with the notification feature, its two settings, and a note that Steam's "notifications while in game" preference and Do Not Disturb can suppress the toast
- [ ] 8.2 Note the no-dedupe limitation (a revisited system notifies again) in `README.md`
- [ ] 8.3 Update `AGENTS.md` — new settings keys, new callables, the `notify` field on the event, and the `index.tsx` plugin-load listener
- [ ] 8.4 Add a `CHANGELOG.md` entry under `[Unreleased]`

## 9. Verification

- [ ] 9.1 Run the full test suite plus lint and typecheck; confirm everything passes
- [ ] 9.2 Package with `npm run package`, deploy to the device, and confirm on-device: a green arrival with notifications on raises a toast over the running game with the panel closed
- [ ] 9.3 Confirm on-device that tapping the toast opens the plugin's quick access tab
- [ ] 9.4 Confirm on-device that opening and refreshing the panel raises no toast, and that a red arrival raises none
