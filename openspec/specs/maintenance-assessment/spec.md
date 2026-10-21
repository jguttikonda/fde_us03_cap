# maintenance-assessment Specification

## Purpose

Defines evidence-grounded maintenance assessment of AOG repair feasibility, root cause, recurring failures, repair duration, and return-to-service timing for human decision support.

## Requirements

### Requirement: Maintenance evidence is validated before assessment

The Maintenance assessment MUST use the case identity, defect, aircraft metadata, work-order state, maintenance history, engineering constraints, safety conditions, and part dependencies when available. It MUST report missing or invalid required inputs instead of filling them with inferred facts. (ARD-MNT-001, ARD-MNT-002, ARD-DAT-004, ARD-DAT-005, ARD-DAT-009)

#### Scenario: Complete maintenance evidence is accepted

- **WHEN** required case and maintenance inputs are valid and source-backed
- **THEN** the assessment retains their source references and evaluates the repair path without changing the recorded facts (ARD-MNT-001, ARD-MNT-002, ARD-DAT-004)

#### Scenario: Required work-order information is missing

- **WHEN** work-order fields required for a repair estimate are missing or invalid
- **THEN** the result identifies each missing field, remains provisional or requests information, and does not invent a repair duration (ARD-MNT-007, ARD-GOV-005, ARD-RES-004)

### Requirement: Repairability and ground-time estimates remain evidence-bounded

The Maintenance result MUST classify repairability as feasible, uncertain, or not feasible and MUST provide a supported ground-time estimate or state why one cannot be supported. (ARD-MNT-003, ARD-MNT-004, ARD-PRN-005)

#### Scenario: Repairability is supported by current evidence

- **WHEN** the work order and technical evidence support a repair path and duration
- **THEN** the result reports the repairability classification, required actions, estimated ground time, source evidence, assumptions, and confidence (ARD-MNT-003, ARD-MNT-004, ARD-MNT-005)

#### Scenario: Repair duration cannot be established

- **WHEN** technical evidence does not support a repair-duration estimate
- **THEN** the result states why the estimate is unavailable, exposes the missing or conflicting evidence, and marks the assessment uncertain or escalated (ARD-MNT-004, ARD-RES-004, ARD-GOV-003..005)

### Requirement: Root cause and recurring failures retain provenance

The Maintenance result MUST report a root-cause category with confidence and supporting evidence references, and MUST report matching recurring-failure counts and time windows when history supports them. (ARD-MNT-009, ARD-MNT-010, ARD-DAT-004..006)

#### Scenario: Recurring failure supports a preferred-part request

- **WHEN** source-backed history shows at least three matching failures in the configured 90-day window and engineering evidence identifies a preferred replacement
- **THEN** Maintenance reports the count, window, evidence, and preferred-part request for Materials & Logistics evaluation without treating that part as authorized or available (ARD-MNT-009, ARD-MLG-009, ARD-SYS-004)

#### Scenario: History is incomplete or contradictory

- **WHEN** maintenance history is missing, stale, or contradictory
- **THEN** the result separates confirmed occurrences from assumptions and unknowns, and does not assert a recurring-failure count unsupported by the available records (ARD-DAT-005, ARD-GOV-004..005, ARD-RES-006)

### Requirement: Safety and engineering status is reported without approval claims

The Maintenance result MUST expose documented safety and engineering approval evidence for each repair path. Missing approval MUST prevent a final feasible disposition; the agent MUST NOT certify airworthiness or approve work. (ARD-MNT-006, ARD-SEC-008, ARD-GOV-006, ARD-GOV-008)

#### Scenario: Approval evidence is missing

- **WHEN** safety or engineering approval evidence is absent or pending
- **THEN** the path remains uncertain or escalated, the missing approval is identified, and no approval is inferred from the agent result (ARD-MNT-006, ARD-GOV-003..005, ARD-GOV-008)

#### Scenario: Approval evidence is present

- **WHEN** a source reports an approval state for a repair path
- **THEN** the result reports the source-backed state and responsible human role as evidence only, without claiming the agent approved or certified the path (ARD-MNT-006, ARD-SEC-008)

### Requirement: Return-to-service timing includes need-by assessment

The Maintenance result MUST report supported repair-duration and parts-readiness inputs, the return-to-service estimate, whether it meets the AOG case need-by time, estimated repair labor cost, and ETA-related risks. If required timing inputs are unavailable, it MUST retain that uncertainty. (ARD-MNT-005, ARD-MNT-010, ARD-DAT-006, ARD-GOV-005)

#### Scenario: Parts readiness supports the repair estimate

- **WHEN** the Materials & Logistics response provides a source-backed parts-ready time and required repair duration
- **THEN** Maintenance reports both components, the derived return-to-service estimate, the need-by comparison, labor cost, and assumptions used in the timing estimate (ARD-MNT-004, ARD-MNT-010, ARD-MLG-005..006)

#### Scenario: Parts timing is unavailable or degraded

- **WHEN** the required part is unavailable, stale, or has conflicting lead-time evidence
- **THEN** the return-to-service estimate is marked provisional or unavailable, the degradation is visible, and confidence is reduced or escalation is required (ARD-MNT-007..008, ARD-GOV-003..005, ARD-RES-001, ARD-RES-006)
