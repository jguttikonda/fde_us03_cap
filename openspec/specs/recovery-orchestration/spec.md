# recovery-orchestration Specification

## Purpose

Defines Controller-owned, case-scoped orchestration that validates AOG intake, coordinates existing specialists, preserves degraded evidence, and produces an unranked handoff requiring human approval.

## Requirements

### Requirement: AOG intake is validated before routing

The Controller MUST validate each intake against the versioned AOG case contract and required orchestration fields before routing. Invalid intake MUST return field-level findings and MUST NOT invoke a specialist or produce a handoff. (ARD-CTL-001..002, ARD-DAT-001..002/009..010)

#### Scenario: Valid intake is accepted

- **WHEN** an intake contains all required case fields and a supported schema version
- **THEN** the Controller creates a case-scoped workflow record with the supplied case, trace, and correlation identifiers (ARD-DAT-001..003)

#### Scenario: Invalid or unsupported intake is rejected

- **WHEN** required fields are absent, invalid, or use an unsupported schema version
- **THEN** the Controller returns field-level findings, records the validation failure, and invokes no specialist (ARD-CTL-002, ARD-DAT-009..010)

### Requirement: Routing and source health are explicit

The Controller MUST record source health and the agents selected or omitted for a case with deterministic reasons. Routing MUST use only the defined specialist roles and MUST NOT infer a complete analysis from an unavailable source. (ARD-CTL-003..004, ARD-SYS-003, ARD-SEC-003)

#### Scenario: Normal case routes to required specialists

- **WHEN** a valid AOG case requires maintenance, material, and operational impact analysis
- **THEN** Maintenance, Materials & Logistics, and Operations are selected with the case's correlation context, and routing reasons are recorded (ARD-CTL-004, ARD-DAT-003)

#### Scenario: A specialist is intentionally omitted or its source is unavailable
- **WHEN** policy omits a specialist or a required source is unavailable
- **THEN** the Controller records the omission or source health and reason, identifies the affected analysis as missing, and does not mark the workflow complete (ARD-CTL-003..004/008, ARD-RES-003..004)

#### Scenario: An omitted specialist is not invoked

- **WHEN** a valid routing decision omits a specialist with a deterministic reason
- **THEN** the Controller does not invoke that role, preserves the reason in the case handoff, and reports the omitted analysis as missing (ARD-CTL-003..004/008, ARD-RES-003..004)

#### Scenario: An unavailable selected source is not treated as healthy

- **WHEN** a selected specialist has an explicitly unavailable source-health record
- **THEN** the Controller skips that specialist invocation, records a structured candidate-local failure, and returns a partial or escalated handoff with source and analysis status visible (ARD-CTL-003..004/008, ARD-GOV-005, ARD-RES-003..004)

### Requirement: Shared case context preserves evidence and peer exchanges

The Controller MUST own case-scoped shared workflow state and preserve specialist inputs, validated results, evidence references, missing data, warnings, conflicts, and the ordered Maintenance H3/Materials & Logistics H4 exchange. (ARD-CTL-005, ARD-SYS-002/004, ARD-DAT-003..006, ARD-OBS-001..003)

#### Scenario: Specialist results and H3/H4 are recorded

- **WHEN** specialist results and a peer exchange are received for a case
- **THEN** the Controller context records their case, trace/correlation, request/exchange identifiers, status, evidence references, and event order (ARD-CTL-005, ARD-SYS-004, ARD-OBS-002)

#### Scenario: Context append fails

- **WHEN** a required context append fails
- **THEN** the workflow reports an incomplete structured failure and does not claim the exchange or case was fully recorded (ARD-RES-003..006, ARD-OBS-003, ARD-SEC-009)

### Requirement: Specialist invocation and results are bounded and validated

The Controller MUST invoke required specialists through their typed boundaries, validate each result against its shared and role-specific contract, and bound asynchronous calls by configured timeouts. Invalid, missing, timed-out, or failed results MUST remain explicit. (ARD-CTL-006/008, ARD-TEC-002..005, ARD-DAT-001/009..010, ARD-NFR-001..002)

#### Scenario: Valid specialist results are accepted

- **WHEN** a specialist returns a supported result with valid evidence references
- **THEN** the Controller accepts it for aggregation without changing its domain facts or implying approval (ARD-CTL-006, ARD-DAT-006)

#### Scenario: Specialist returns invalid output or times out

- **WHEN** a specialist result is malformed, references unavailable evidence, fails, or exceeds its configured timeout
- **THEN** the Controller records a structured failure or partial result, identifies the missing analysis, and applies the confidence/escalation policy (ARD-DAT-008..010, ARD-RES-002..004, ARD-NFR-001)

### Requirement: Aggregation preserves missing evidence and conflicts

The Controller MUST aggregate only validated specialist results, retain conflicting values with their sources, and expose missing data, warnings, unknowns, and failure impact. Missing required results or material conflicts MUST prevent a complete workflow status. (ARD-CTL-006..008, ARD-DAT-004..006, ARD-GOV-004..005, ARD-RES-004/006)

#### Scenario: Specialist findings materially conflict

- **WHEN** Maintenance, Materials & Logistics, or Operations provide incompatible material findings
- **THEN** the Controller retains both values and evidence references, marks the case provisional or escalation-required, and defers adjudication to a human (ARD-CTL-007..008, ARD-GOV-004)

#### Scenario: A required result is missing

- **WHEN** a required specialist fails, times out, or returns only partial data
- **THEN** the Controller identifies supported and unsupported conclusions separately, lowers confidence or escalates, and does not present the package as complete (ARD-CTL-008, ARD-RES-003..004, ARD-GOV-003..005)

### Requirement: Candidate options receive per-candidate specialist evaluation

The Controller MUST construct supported repair-original, repair-preferred/alternate, aircraft-swap, and delay candidates from validated case evidence, including applicable sourcing and package-load inputs. It MUST invoke Maintenance and Materials & Logistics concurrently for each candidate, then invoke Operations for each candidate using its readiness ETA. (ARD-CTL-018)

#### Scenario: Each supported candidate is evaluated through all required domains

- **WHEN** validated case evidence supports multiple recovery candidates
- **THEN** each candidate has its own Maintenance and Materials & Logistics results and an Operations assessment tied to that candidate's readiness evidence and identifier (ARD-CTL-018, ARD-CTL-006)

#### Scenario: Required candidate evidence is missing

- **WHEN** a candidate lacks a required source, readiness ETA, or package-load input
- **THEN** that candidate's analysis remains partial or undetermined with the missing input named, and no value is inferred from another candidate (ARD-CTL-008, ARD-GOV-005, ARD-RES-004)

#### Scenario: Per-candidate results remain unranked

- **WHEN** Operations returns assessments for the candidate set
- **THEN** the Controller preserves the assessments and their costs without assigning a weighted score, relative rank, or final recommendation (ARD-CTL-011..016, ARD-SYS-005)

### Requirement: Compliance eligibility precedes an unranked handoff

Before handing candidate assessments to the later ranking stage, the Controller MUST exclude candidates that fail airworthiness/engineering approval or part authorization/traceability and record the exclusion reason. It MAY assemble candidates and per-candidate specialist results, but MUST NOT calculate weighted scores, rank candidates, or present a uniquely preferred recovery option in this capability. (ARD-CTL-017..018, ARD-SYS-005)

#### Scenario: Candidate fails compliance eligibility

- **WHEN** a candidate lacks required approval, part authorization, or traceability evidence
- **THEN** it is excluded from the eligible handoff and its reason and source evidence remain visible (ARD-CTL-017, ARD-GOV-005)

#### Scenario: Eligible candidates are handed off without ranking

- **WHEN** candidate assessments pass the compliance gate
- **THEN** the Controller returns them with validated findings, confidence, assumptions, and conflicts but no score, rank, or final decision brief (ARD-CTL-018, ARD-SYS-005)

### Requirement: Human approval remains mandatory and separate

Every orchestration handoff MUST remain advisory and pending human decision. No agent result, confidence value, source state, or degraded mode may approve or execute an operational action; applicable repair or part approval requires the authorized human roles. (ARD-PRN-001..002, ARD-GOV-001..008, ARD-SEC-002..003, ARD-TST-005)

#### Scenario: High-confidence handoff still requires human approval

- **WHEN** all specialist results are complete and confidence is at least 0.70
- **THEN** the workflow remains pending approval and no operational action is performed (ARD-GOV-001/008, ARD-PRN-001..002)

#### Scenario: Low confidence or conflict escalates

- **WHEN** confidence is below 0.50 or material evidence conflicts
- **THEN** the Controller marks escalation required and approval remains deferred regardless of any aggregate confidence (ARD-GOV-003..004/008)

#### Scenario: No operational execution is exposed

- **WHEN** a caller requests booking, ordering, transferring, dispatching, delaying, or another operational action through orchestration
- **THEN** the request is rejected or returned as an advisory handoff, with no write or execution capability invoked (ARD-PRN-002, ARD-SEC-001..003, ARD-GOV-008)

### Requirement: Case state and audit data are isolated and correlated

Controller workflow state and audit events MUST be isolated by case and MUST carry the case, trace/correlation, component, status, timestamp, and schema identifiers necessary to reconstruct the external workflow trajectory without private chain-of-thought. (ARD-RES-007, ARD-OBS-001..004, ARD-SEC-007/009)

#### Scenario: Concurrent cases remain isolated

- **WHEN** multiple AOG cases are orchestrated concurrently and one case experiences a failure
- **THEN** each case retains only its own inputs, results, conflicts, failures, and audit events (ARD-RES-007)

#### Scenario: Audit trajectory is explainable

- **WHEN** the Controller validates, routes, invokes a specialist, aggregates, or escalates
- **THEN** it emits correlated structured events with concise rationale and evidence references, without recording private chain-of-thought (ARD-OBS-001..004, ARD-PRN-008)