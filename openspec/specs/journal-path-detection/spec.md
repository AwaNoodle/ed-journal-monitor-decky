## Purpose

Locate the Elite Dangerous journal directory automatically, with a manual override.

## Requirements

### Requirement: Parse Steam library folders configuration
The backend SHALL parse `~/.local/share/Steam/config/libraryfolders.vdf` to discover all Steam library paths on the system.

#### Scenario: Standard Steam Deck with internal storage
- **WHEN** the backend reads `libraryfolders.vdf` containing a single library at `/home/deck/.local/share/Steam`
- **THEN** the backend SHALL return that path as a library location

#### Scenario: Steam Deck with SD card library
- **WHEN** the backend reads `libraryfolders.vdf` containing libraries at `/home/deck/.local/share/Steam` and `/run/media/mmcblk0p1/steamlib`
- **THEN** the backend SHALL return both paths as library locations

#### Scenario: VDF file does not exist
- **WHEN** `libraryfolders.vdf` does not exist at the expected path
- **THEN** the backend SHALL check the fallback path `~/.steam/root/config/libraryfolders.vdf` (symlink)
- **THEN** if neither exists, return an empty list of libraries

### Requirement: Find ED journal directory by scanning compatdata
The backend SHALL search each Steam library's `steamapps/compatdata/359320/pfx/` directory for the Elite Dangerous journal path using a glob pattern.

#### Scenario: ED installed on internal storage
- **WHEN** the compatdata directory at `<library>/steamapps/compatdata/359320/pfx/` exists
- **AND** a directory matching `drive_c/users/*/Saved Games/Frontier Developments/Elite Dangerous/` exists within it
- **AND** that directory contains `Journal*.log` files
- **THEN** the backend SHALL return the full path to the journal directory

#### Scenario: ED installed on SD card
- **WHEN** the SD card library path contains `compatdata/359320/pfx/`
- **THEN** the backend SHALL find the journal directory the same as internal storage

#### Scenario: ED not installed (no compatdata)
- **WHEN** no Steam library contains `compatdata/359320/`
- **THEN** the backend SHALL return None

#### Scenario: ED installed but never launched (no journal files)
- **WHEN** the compatdata directory exists but the `Saved Games/Frontier Developments/Elite Dangerous/` directory does not exist
- **THEN** the backend SHALL return None (will be found on re-scan after first launch)

### Requirement: Cache discovered journal path in settings
The backend SHALL persist the discovered journal path in `DECKY_PLUGIN_SETTINGS_DIR` for use across plugin restarts.

#### Scenario: Path found and cached
- **WHEN** the backend successfully discovers a journal directory
- **THEN** the backend SHALL write the path to plugin settings

#### Scenario: Cached path verified on startup
- **WHEN** the plugin starts and a cached journal path exists in settings
- **THEN** the backend SHALL verify the path still exists and contains `Journal*.log` files
- **THEN** if valid, use the cached path without re-scanning
- **THEN** if invalid, clear the cache and attempt VDF scan

### Requirement: Manual journal path configuration
The backend SHALL accept a manually configured journal path from the UI and validate it.

#### Scenario: User sets manual path
- **WHEN** the user provides a journal directory path via the UI
- **THEN** the backend SHALL verify the directory exists and contains `Journal*.log` files
- **THEN** if valid, save to settings and use as the journal path
- **THEN** if invalid, return an error to the frontend

### Requirement: Handle SD card ejection and reinsertion
The backend SHALL handle Steam library paths that become temporarily unavailable.

#### Scenario: SD card ejected after path cached
- **WHEN** the cached journal path no longer exists (SD card removed)
- **THEN** the backend SHALL NOT clear the cached path
- **THEN** the backend SHALL report the path as temporarily unavailable

#### Scenario: SD card reinserted
- **WHEN** the cached journal path becomes available again
- **THEN** the backend SHALL resume using the cached path
