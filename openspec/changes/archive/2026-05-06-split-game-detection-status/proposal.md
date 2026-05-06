## Why

The plugin currently shows a single status line that conflates game detection with journal/watcher state. When Elite Dangerous is running but the journal path isn't found, the UI says "Idle — waiting for Elite Dangerous", which is actively misleading. Users have no visual feedback that the game has been detected, and no way to distinguish between "ED isn't running" vs "ED is running but something is wrong with the journal/watcher".

## What Changes

- Split the single status display into two independent status fields: **ED Status** and **Journal Status**
- ED Status shows: Not Running / Running
- Journal Status shows: Journal Not Found / Found, Watcher Not Running / Watching & Uploading
- "Watcher Not Running" is contextual: neutral when ED isn't running, a warning (⚠️) when ED is running
- Backend tracks ED running state in-memory, exposed via `get_status()` and a new `ed_state_change` event
- Frontend calls new `set_ed_running(bool)` callable when SteamClient fires, backend persists state and emits event
- This ensures the UI stays in sync even when the panel is opened after ED has already started

## Capabilities

### New Capabilities
- `game-detection-status`: Backend tracking of ED running state, callable to set it, event emission on change, and two-field UI display splitting ED Status from Journal Status

### Modified Capabilities
- `game-lifecycle`: Frontend must call `set_ed_running()` in addition to start/stop watcher when ED starts/stops
- `plugin-ui`: Replace single status line with two independent status fields (ED Status / Journal Status)

## Impact

- `main.py` — new `set_ed_running()` callable, in-memory `ed_running` state, `ed_state_change` event emission, `get_status()` returns `ed_running`
- `src/index.tsx` — call `set_ed_running(true/false)` in `handleAppStart`
- `src/Content.tsx` — two Field rows for ED Status / Journal Status, listen to `ed_state_change` event
- Existing `game-lifecycle` and `plugin-ui` specs updated
