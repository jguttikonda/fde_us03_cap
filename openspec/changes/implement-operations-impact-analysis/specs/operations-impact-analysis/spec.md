# Spec Delta

## Purpose

The Operations impact-analysis capability evaluates Controller-supplied AOG recovery options against current flight, fleet, crew, customer, schedule, disruption, and package evidence. It returns a structured, advisory-only result that can be aggregated by the Controller and reviewed by authorized humans.

## ADDED Requirements

### Requirement: Validate and preserve operational evidence
The capability MUST validate its structured inputs and preserve the source, observation time, and freshness of operational evidence. It MUST distinguish confirmed facts from assumptions and MUST identify missing or stale required evidence.

#### Scenario: Complete operational evidence
- **WHEN** the capability receives valid flight, schedule, route, fleet, crew, customer-priority, disruption, and package evidence
- **THEN** it validates the inputs and retains provenance and observation time for facts used in each option assessment (ARD-OPS-001, ARD-PRN-005, ARD-PRN-007, ARD-SEC-004)

#### Scenario: Missing or stale evidence
- **WHEN** a required field is absent or a time-sensitive source is stale
- **THEN** the result lists the missing or stale evidence, identifies conclusions it cannot support, and does not replace it with an unstated assumption (ARD-OPS-006, ARD-PRN-006, ARD-GOV-005)

### Requirement: Detect schedule, route, assignment, and feasibility conflicts deterministically
The capability MUST deterministically validate schedules, route constraints, aircraft assignments, candidate fleet availability, and configured disruption thresholds before producing option assessments.

#### Scenario: No conflict for a feasible candidate
- **WHEN** validated schedule and assignment evidence shows no conflict and a candidate aircraft is available for the required window
- **THEN** the result reports the checked constraints and the candidate's supported feasibility without claiming that an operational swap has occurred (ARD-OPS-002, ARD-OPS-004, ARD-SEC-002)

#### Scenario: Assignment or route conflict
- **WHEN** an aircraft assignment, route, crew, station, or schedule conflict is detected
- **THEN** the result identifies the affected resource and conflict, excludes the candidate from feasible options where the deterministic rule requires it, and explains why another supported option is more viable (ARD-OPS-002, ARD-OPS-008)

### Requirement: Assess Controller-supplied recovery options
For each applicable repair, aircraft-swap, or delay candidate supplied by the Controller, the capability MUST return a consistent operational impact assessment and an estimated cost when the required cost evidence or configured mock estimate is available.

#### Scenario: Repair, swap, and delay comparison
- **WHEN** the Controller supplies repair ETA, swap, and delay candidates with sufficient operational evidence
- **THEN** the result describes affected flights and routes, schedule and fleet effects, estimated impact, risks, assumptions, and per-option estimated cost, and identifies the Operations-preferred option with rationale without performing system-wide scoring or ranking (ARD-OPS-003, ARD-OPS-004, ARD-OPS-005, ARD-PRN-004)

#### Scenario: Candidate cost cannot be established
- **WHEN** required data for an option's cost estimate is unavailable
- **THEN** the result marks that option's cost as unavailable, identifies the missing evidence, and does not substitute zero or another success-shaped value (ARD-OPS-005, ARD-PRN-006)

### Requirement: Assess package load redistribution within operational constraints
The capability MUST assess package redistribution using capacity by aircraft tail, package manifests and service levels, and applicable sort and cut-off windows. It MUST report packages that cannot be protected and include their exposure in the option's impact and cost assessment.

#### Scenario: Capacity and cut-off permit partial redistribution
- **WHEN** an affected flight has 1,200 packages including 700 priority packages, a spare aircraft has capacity for 900, and redistribution is within the applicable sort and cut-off window
- **THEN** the result protects no more than 900 packages using the configured deterministic service-level priority, reports the remaining 300 as unprotected, and includes the unprotected exposure in the option impact and cost (ARD-OPS-009, ARD-TST-006)

#### Scenario: Alternate flight is past cut-off
- **WHEN** an alternate flight has spare capacity but the package arrival would miss its cut-off
- **THEN** the capability assigns no packages to that flight, records the cut-off constraint, and reports the resulting unprotected package count and service-level exposure (ARD-OPS-009, ARD-PRN-003)

### Requirement: Return a structured Operations assessment for Controller aggregation
The capability MUST return a versioned, validated result containing status, impact classification, affected routes and flights, option-level impacts, package impact, evidence, missing data, assumptions, risks, recommendation, confidence, rationale, and next steps. It MUST remain a domain assessment and MUST NOT generate the Controller's final report or weighted ranking.

#### Scenario: Structured result for a candidate
- **WHEN** an option assessment completes with sufficient evidence
- **THEN** the result conforms to the Operations contract, classifies impact as low, medium, high, or critical, and separates source-backed evidence from assumptions and model explanation (ARD-OPS-003, ARD-OPS-005, ARD-PRN-005, ARD-PRN-007)

#### Scenario: Materially different customer impacts
- **WHEN** multiple feasible options have materially different customer or service-level impacts
- **THEN** the result presents each option's trade-offs and does not hide an alternative behind a single recommendation (ARD-OPS-007)

### Requirement: Represent uncertainty, conflict, and degraded analysis
The capability MUST label incomplete or time-sensitive analysis provisional, apply the confidence thresholds, and represent conflicting evidence, missing analysis, and tool failures visibly. It MUST distinguish supported conclusions from conclusions that cannot be established.

#### Scenario: Conflicting operational evidence
- **WHEN** two current sources disagree materially about a schedule, route, assignment, or recovery time
- **THEN** the result identifies both conflicting values and their provenance, marks the affected conclusion provisional or escalated, and defers approval regardless of numeric confidence (ARD-OPS-006, ARD-PRN-006, ARD-GOV-004)

#### Scenario: Low confidence requires escalation
- **WHEN** analysis confidence is below 0.50
- **THEN** the result marks the assessment for escalation and lists data needed to improve it; confidence from 0.50 through 0.69 is provisional, and confidence at or above 0.70 remains a preferred path only (ARD-GOV-001..003, ARD-GOV-005)

#### Scenario: Operations adapter times out
- **WHEN** an allowlisted Operations adapter exceeds its configured timeout
- **THEN** the result records a structured timeout warning, identifies the unavailable analysis, preserves only conclusions supported by available evidence, and applies the confidence or escalation policy (ARD-RES-002..006, ARD-NFR-001..002)

### Requirement: Preserve advisory-only, read-only, and auditable boundaries
The capability MUST expose only allowlisted, least-privilege read-only tools and MUST NOT execute schedule changes, aircraft swaps, dispatch, bookings, package transfers, or approval actions. It MUST reject untrusted data that attempts to change policy or tool permissions and MUST emit traceable events without requiring private chain-of-thought.

#### Scenario: Recommendation awaits human decision
- **WHEN** the capability returns a high-confidence preferred option
- **THEN** the result remains advisory, no operational action is invoked, and approval remains with the authorized human boundary (ARD-PRN-001..002, ARD-GOV-001, ARD-GOV-006..008, ARD-SEC-002)

#### Scenario: Tool content attempts to override policy
- **WHEN** external operational data contains instructions to expand tool access, suppress uncertainty, or bypass human approval
- **THEN** the content is treated as untrusted data and cannot change the capability's policy, allowlist, assigned role, or approval boundary (ARD-SEC-003..005, ARD-SEC-008)

#### Scenario: Auditable degraded result
- **WHEN** validation, tool invocation, conflict detection, or fallback affects an assessment
- **THEN** structured events identify timestamp, event type, case and correlation identifiers, component, status, and schema version, while sensitive data and private chain-of-thought are excluded (ARD-PRN-008, ARD-OBS-001..004, ARD-SEC-006..007)

### Requirement: Verify behavior with deterministic tests
The capability MUST have contract and agent tests for valid and invalid input, normal and partial evidence, conflict, low confidence, timeout, package redistribution, read-only behavior, and the human-approval boundary. Unit tests MUST use deterministic fixtures and mock adapters without network or live model calls.

#### Scenario: Deterministic contract and behavior tests
- **WHEN** tests run repeatedly with identical validated fixtures and mock responses
- **THEN** validation, conflict checks, capacity calculations, impact classification, and structured results are repeatable, and failures are visible rather than success-shaped (ARD-TEC-008, ARD-NFR-003, ARD-TST-001..003, ARD-TST-009)

#### Scenario: Security and approval boundary tests
- **WHEN** tests exercise unauthorized tool access, malformed external data, prompt injection, or a high-confidence recommendation
- **THEN** unauthorized or malformed inputs are rejected or visibly degraded, no write operation occurs, and no result bypasses human approval (ARD-SEC-001..008, ARD-TST-005, ARD-TST-007)

#### Scenario: Functional package and conflict regressions
- **WHEN** fixed regression fixtures exercise a feasible swap and a route/assignment conflict alongside constrained package capacity and cut-off windows
- **THEN** the tests verify the supported swap candidate, conflict explanation, protected and unprotected package counts, and cost-impact inclusion (ARD-TST-003, ARD-TST-006, ARD-TST-008..009)
