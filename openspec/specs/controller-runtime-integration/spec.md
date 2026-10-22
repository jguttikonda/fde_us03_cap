# controller-runtime-integration Specification

## Purpose

Defines the runtime binding between Controller routing decisions and existing specialist contracts so an integrated AOG workflow remains typed, bounded, case-isolated, and safely unranked.

## Requirements

### Requirement: Specialist adapters conform to existing input contracts

The Controller MUST translate each validated candidate request into inputs accepted by the existing Maintenance and Materials & Logistics boundaries. The translation MUST preserve case identity, candidate identity, source evidence, readiness, and candidate-specific sourcing data without fabricating unsupported values. (ARD-CTL-006/018, ARD-DAT-003..006/009..010)

#### Scenario: Candidate inputs map to specialist contracts
- **WHEN** a candidate has validated case, evidence, readiness, and sourcing inputs
- **THEN** each specialist receives a valid role-specific request containing only that candidate's supported values and evidence references (ARD-CTL-006/018, ARD-DAT-004..006)

#### Scenario: Candidate input is missing or invalid
- **WHEN** a required specialist input cannot be mapped or its evidence reference does not resolve
- **THEN** that specialist is not given a success-shaped request; the candidate result names the missing or invalid input and remains partial or escalated (ARD-DAT-009..010, ARD-GOV-005, ARD-RES-004)

#### Scenario: H3/H4 recording fails
- **WHEN** appending either peer-exchange record fails for a repair candidate
- **THEN** the Controller preserves both specialist outcomes, marks the exchange missing, and keeps that candidate partial or escalated without affecting other candidates (ARD-CTL-005..006, ARD-RES-003..005/007)

### Requirement: Operations evaluation has a bounded deadline

Each per-candidate Operations invocation MUST be bounded by configured timeout policy. A timeout MUST create a structured candidate-local failure, name Operations analysis as missing, and lower confidence or escalate without erasing other candidate results. (ARD-RES-002..005/007, ARD-NFR-001..002, ARD-CTL-008/018)

#### Scenario: Operations exceeds its deadline
- **WHEN** Operations does not return before its configured deadline for a candidate
- **THEN** the Controller records a timeout with the candidate and request identifiers, preserves other candidates' results, and returns a partial or escalated handoff with the missing analysis visible (ARD-RES-002..004, ARD-GOV-003..005)

#### Scenario: Operations completes before its deadline
- **WHEN** Operations returns a validated result before the deadline
- **THEN** the Controller retains the per-candidate package, impact, cost, warnings, and evidence without changing Operations domain facts (ARD-CTL-006/018, ARD-OPS-005/009)

#### Scenario: Timed-out synchronous work remains worker-bounded
- **WHEN** a synchronous Operations worker continues after the Controller deadline
- **THEN** the timed-out request returns candidate-local failure, its worker slot remains occupied until completion, and further work is rejected at the configured capacity rather than queued without bound (ARD-RES-002/005, ARD-NFR-001..002)

### Requirement: ADK response preserves the deterministic workflow contract

The Controller ADK entry point MUST expose the versioned deterministic completed workflow result, including the ranked decision brief, compliance exclusions, evidence gaps, confidence disposition, and human-gate state. It MUST NOT substitute model-generated success or alter deterministic scores. The response MUST remain advisory and MUST expose no operational action capability. (ARD-TEC-002/005, ARD-CTL-009..010/016..018, ARD-GOV-008, ARD-SEC-001..003)

#### Scenario: Valid deterministic workflow response
- **WHEN** the deterministic workflow returns a validated recommendation
- **THEN** the ADK boundary returns the typed report with ranking, evidence gaps, exclusions, status, and pending human gate intact (ARD-DAT-006/010, ARD-CTL-016, ARD-GOV-008)

#### Scenario: Workflow validation or execution fails
- **WHEN** deterministic workflow validation fails or its result cannot be validated
- **THEN** the ADK boundary returns an explicit structured failure and does not replace it with a success-shaped narrative (ARD-DAT-008..010, ARD-RES-003/006)

#### Scenario: Compliance exclusion and conflicting evidence remain visible
- **WHEN** a candidate fails a deterministic compliance check or its evidence conflicts
- **THEN** the report retains the exclusion reason or conflict, assigns no score or rank to an excluded candidate, and escalates or marks provisional as required (ARD-CTL-017, ARD-GOV-002..005)

#### Scenario: Human approval remains pending
- **WHEN** the Controller returns any recommendation, including a high-confidence or close-scored result
- **THEN** the response preserves the pending human gate, requires the Ops lead and Maintenance/airworthiness authority approvals, and exposes no approval decision or operational action (ARD-GOV-001/006..008, ARD-PRN-001..002)

### Requirement: Concurrent Controller cases remain isolated

The Controller MUST isolate workflow state, specialist requests/results, failures, and audit events by case and trace/correlation context during concurrent execution. A failure in one case MUST NOT alter or expose another case's result or status. (ARD-RES-007, ARD-OBS-001..004, ARD-SEC-007/009, ARD-NFR-002)

#### Scenario: Concurrent cases complete independently
- **WHEN** two cases run concurrently with different trace contexts and one specialist fails for only one case
- **THEN** each handoff contains only its own case data and events, and the failure changes only the affected case's status (ARD-RES-007, ARD-OBS-002..003)

#### Scenario: Concurrent case audit records remain correlated
- **WHEN** lifecycle events are emitted for two concurrent cases
- **THEN** every event remains append-only and carries the correct case, trace/correlation, component, status, timestamp, and schema metadata (ARD-OBS-001..004, ARD-SEC-009)