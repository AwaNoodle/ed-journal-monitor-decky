## Context

The plugin UI displays a "Journal Status" field. When the watcher is active it reads "🟢 Watching & Uploading". The phrase "& Uploading" is redundant because the "Recent Activity" section already surfaces upload events as they happen.

## Goals / Non-Goals

**Goals:**
- Remove "& Uploading" from the active watcher status label
- Keep the spec and source in sync

**Non-Goals:**
- Changes to any other status state
- Changes to the "Recent Activity" section
- Any backend changes

## Decisions

Single string-literal change in `src/Content.tsx` at the `getJournalStatus` helper (line ~197). No abstraction or config needed — this is a display-copy tweak with no runtime logic impact.

The `plugin-ui` spec scenario for "Plugin watching (ED running)" is updated to match so the spec remains the source of truth for UI text.

## Risks / Trade-offs

None — purely cosmetic, no logic changes, no data migration needed.
