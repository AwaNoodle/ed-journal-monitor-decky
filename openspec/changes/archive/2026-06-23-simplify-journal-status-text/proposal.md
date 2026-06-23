## Why

The "Journal Status" field currently shows "🟢 Watching & Uploading" when the watcher is active, but the "Recent Activity" section already makes uploading visible. The redundant "& Uploading" wording adds noise without adding information.

## What Changes

- The "Journal Status" active state text changes from "🟢 Watching & Uploading" to "🟢 Watching"
- No other status states are affected ("⚠️ Found, Not Watching", "📂 Found", "🔍 Not Found" remain unchanged)

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `plugin-ui`: The "Journal Status" active state label changes from "Watching & Uploading" to "Watching"

## Impact

- `src/Content.tsx`: one string literal change
- `openspec/specs/plugin-ui/spec.md`: update the scenario text to reflect the new label
