## MODIFIED Requirements

### Requirement: Display upload statistics
The frontend SHALL display upload counts received from backend events.

#### Scenario: Statistics displayed
- **WHEN** the backend emits a `status_update` event
- **THEN** the panel SHALL update the displayed successful upload count and failed upload count
