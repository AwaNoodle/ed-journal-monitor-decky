## Context

The plugin currently shows a single status line that conflates two independent concerns: whether Elite Dangerous is running, and whether the journal file is being watched. The backend has no awareness of ED's running state — game detection lives entirely in the frontend (`index.tsx`) via SteamClient notifications. The UI (`Content.tsx`) only knows about watcher state from `get_status()`, so if the panel is opened after ED has already started, there's no way to know the game is running.

## Goals / Non-Goals

**Goals:**
- Split the UI status into two independent fields: ED Status and Journal Status
- Backend tracks ED running state in-memory, so `get_status()` can return it regardless of when the panel opens
- Frontend notifies backend when ED starts/stops via a new callable
- Backend emits `ed_state_change` event so the UI updates in real-time
- Journal Status shows a precedence chain: Not Found → Found/Not Watching → Watching & Uploading
- "Watcher Not Running" is contextual: ⚠️ when ED is running, neutral when ED is not running

**Non-Goals:**
- Auto-detecting ED running state from the backend (e.g., process scanning) — we rely on SteamClient notifications
- Persisting ED running state to disk — it's ephemeral, re-derived from SteamClient on plugin reload
- Adding a "reason" string to the "Watcher Not Running" state (disabled, startup failed, etc.) — can be added later

## Decisions

### 1. Backend tracks ED state, frontend is the source of truth

**Decision**: Frontend calls `set_ed_running(bool)` on game start/stop. Backend stores in-memory and emits event.

**Rationale**: The backend can't detect ED running on its own (no process scanning on SteamOS). SteamClient notifications are the only reliable source, and they arrive on the frontend. Storing in the backend ensures `get_status()` can return the state even when the panel opens late.

**Alternative considered**: Frontend-only state shared via React context. Rejected because `get_status()` is the single source of truth for panel initialization, and it lives in the backend.

### 2. In-memory state, not persisted

**Decision**: `ed_running` is an instance variable on the Plugin class, not saved to settings.

**Rationale**: The state is ephemeral — if the plugin reloads, SteamClient will re-fire notifications. No reason to persist to disk.

### 3. Two independent status fields in UI

**Decision**: Replace the single `getStatusText()` with two Field components: "ED Status" and "Journal Status".

**Rationale**: The two concerns are independent and have different failure modes. Combining them hides the "ED running but journal not found" case.

**Status values:**

| Field | Value | Display |
|-------|-------|---------|
| ED Status | not running | ⚪ Not Running |
| ED Status | running | 🟢 Running |
| Journal Status | not_found | 🔍 Not Found |
| Journal Status | found_idle | 📂 Found (neutral when ED not running, ⚠️ when ED running) |
| Journal Status | watching | 🟢 Watching & Uploading |

### 4. Journal Status precedence chain

**Decision**: Journal Status follows a strict precedence — "Not Found" takes priority over "Not Watching" over "Watching".

**Rationale**: You can't watch what you haven't found. Showing "Not Found" when the path is missing is more useful than showing "Not Watching".

## Risks / Trade-offs

- **[SteamClient notification miss]** → If the plugin loads after ED has already started, the SteamClient won't re-fire the start notification. Mitigation: `get_status()` returns the last-known `ed_running` state from backend. On fresh plugin load, `ed_running` defaults to `false`, which is a safe default (user sees "Not Running" and can investigate).
- **[State drift]** → If `set_ed_running` callable fails silently, backend and frontend could disagree. Mitigation: UI initializes from `get_status()` on mount, and listens to `ed_state_change` for updates. If the callable fails, the frontend still has its own SteamClient notification as a fallback for display purposes — but we should log the failure.
