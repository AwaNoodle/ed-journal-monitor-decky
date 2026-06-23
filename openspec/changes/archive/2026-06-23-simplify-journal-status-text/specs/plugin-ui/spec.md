## MODIFIED Requirements

### Requirement: Display plugin status panel
The frontend SHALL display a Decky UI panel showing the current state of the journal monitor with two independent status fields.

#### Scenario: Plugin idle (ED not running)
- **WHEN** Elite Dangerous is not running and the watcher is not running
- **THEN** the panel SHALL show "ED Status" as "⚪ Not Running"
- **THEN** the panel SHALL show "Journal Status" as "📂 Found" (if journal path exists) or "🔍 Not Found" (if no path)

#### Scenario: Plugin watching (ED running)
- **WHEN** Elite Dangerous is running and the watcher is active
- **THEN** the panel SHALL show "ED Status" as "🟢 Running"
- **THEN** the panel SHALL show "Journal Status" as "🟢 Watching"

#### Scenario: Journal path not found
- **WHEN** the journal path is not detected and no manual path is set
- **THEN** "Journal Status" SHALL display "🔍 Not Found"

#### Scenario: ED running but watcher not active
- **WHEN** Elite Dangerous is running and the watcher is not running and a journal path exists
- **THEN** the panel SHALL show "ED Status" as "🟢 Running"
- **THEN** the panel SHALL show "Journal Status" as "⚠️ Found, Not Watching"
