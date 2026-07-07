## ADDED Requirements

### Requirement: Worth-scanning chip in the Session metric area

The Session section SHALL present an EDSM-sourced "worth scanning" chip for the current system within the existing metric area, using the red/yellow/green verdict from the `edsm-system-lookup` capability. The chip MUST be visibly attributed to EDSM (so the player understands it reflects EDSM's records, not confirmed ground truth) and MUST render a neutral state when a verdict is not available.

#### Scenario: Chip reflects the current verdict

- **WHEN** an EDSM worth-scanning verdict is available for the current system
- **THEN** the Session metric area SHALL show a chip in the corresponding colour (green/yellow/red), labelled as EDSM-sourced

#### Scenario: Neutral chip when lookups are disabled or unavailable

- **WHEN** EDSM auto-lookups are disabled, or a verdict is in flight or unavailable
- **THEN** the chip SHALL render a neutral state rather than a stale or misleading colour

#### Scenario: Chip updates on arrival in a new system

- **WHEN** the player arrives in a new system and a verdict is produced
- **THEN** the chip SHALL update live to reflect the new system's verdict
