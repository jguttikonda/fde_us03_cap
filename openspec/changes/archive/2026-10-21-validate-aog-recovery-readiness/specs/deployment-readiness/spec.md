# Spec Delta

## Purpose

Defines the reproducible local setup, health evidence, rollback guidance, and human-owned readiness records needed to assess an AOG Coordinator release without implying production or operational approval.

## ADDED Requirements

### Requirement: Environment and configuration guidance is reproducible and secret-safe
The project MUST document supported runtime and dependency setup, required non-secret configuration, secret handling, startup, and verification commands so a fresh local checkout can run the deterministic workflow without airline infrastructure. (ARD-DEP-001..002, ARD-NFR-005..007)

#### Scenario: Fresh local environment is prepared
- **WHEN** a team member follows the documented setup on a supported environment
- **THEN** the instructions identify the runtime, locked dependency installation, required environment variables, startup, and test commands, using placeholders for secrets (ARD-DEP-001..002)

#### Scenario: Configuration contains an invalid or missing secret
- **WHEN** a required setting is invalid or a secret is absent
- **THEN** the documented startup or readiness check reports the condition without printing, committing, or substituting a credential (ARD-SEC-006, ARD-NFR-006)

### Requirement: Local readiness checks distinguish mocks from live integrations
The project MUST document a repeatable check of application configuration and available local/mock adapters, and MUST identify which sources are not live or connected. (ARD-DEP-003, ARD-NFR-005)

#### Scenario: Local readiness check succeeds
- **WHEN** the documented local configuration and deterministic adapters are valid
- **THEN** the check reports their readiness and explicitly states that this does not establish live enterprise connectivity, airworthiness, or operational readiness (ARD-DEP-003, ARD-TEC-020)

#### Scenario: A configured local adapter is unavailable
- **WHEN** a required local/mock adapter or configuration check fails
- **THEN** the readiness result names the failure and does not report the system as ready (ARD-DEP-003, ARD-RES-003..004)

### Requirement: Backout guidance restores a known advisory state
The project MUST document an actionable backout to a prior known-good workflow that disables the affected readiness or recommendation capability without removing evidence, enabling writes, or presenting a fabricated successful report. (ARD-DEP-004, ARD-RES-006, ARD-PRN-001..002)

#### Scenario: Readiness or recommendation change is rolled back
- **WHEN** an issue requires disabling the changed capability
- **THEN** the documented backout restores the prior advisory handoff, preserves explicit failure status and audit evidence, and names the tests and checks required before re-enabling it (ARD-DEP-004)

### Requirement: Readiness records separate automation evidence from human decisions
The readiness package MUST retain current verification results, unresolved issues, security considerations, traceability, and draft RAPID and Go/No-Go records without assigning human identities, approvals, or outcomes that have not been supplied. (ARD-DEP-005, ARD-TEC-019..020, ARD-RUB-005..009)

#### Scenario: Automated checks pass while human reviews are pending
- **WHEN** automated verification is complete but peer review or team deliberation has not occurred
- **THEN** the records show the evidence and outstanding items while reviewer assessment and Go/No-Go remain explicitly pending (ARD-DEP-005, ARD-RUB-005..009)

#### Scenario: Verification has an unresolved failure
- **WHEN** a required test, security check, or readiness criterion fails or is unavailable
- **THEN** the record identifies the gap and impact and does not claim the relevant readiness gate passed (ARD-DEP-005, ARD-CAP-003)
