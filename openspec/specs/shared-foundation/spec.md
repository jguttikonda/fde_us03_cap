# shared-foundation Specification

## Purpose

Provides versioned, validated contracts and deterministic shared runtime boundaries so AOG decision-support components exchange traceable evidence and results without hiding degradation or bypassing human authority.

## Requirements

### Requirement: Versioned AOG case contract

The system MUST represent each AOG case with a unique case identifier, aircraft identifier, event type, defect summary, location, event timestamp, creation timestamp, and schema version. Invalid or missing required intake fields MUST be reported explicitly and MUST prevent the case from being treated as valid.

#### Scenario: Complete case intake

- **WHEN** an intake contains all required fields and a supported schema version
- **THEN** the system accepts it as a typed AOG case and preserves its case identifier and timestamps (ARD-DAT-001, ARD-DAT-002, ARD-DAT-010, ARD-CTL-001)

#### Scenario: Missing or invalid intake field

- **WHEN** an intake omits or invalidates a required field
- **THEN** the system returns a structured validation result naming the field and does not treat the case as valid or ready for recommendation (ARD-CTL-001, ARD-CTL-002, ARD-DAT-009)

### Requirement: Provenance-aware evidence contract

The system MUST represent evidence with its source, retrieval time, freshness or validity state, relevant content, supported claim, and explicit distinction from assumptions, warnings, conflicts, and unknowns.

#### Scenario: Evidence has provenance

- **WHEN** validated evidence is included in a case or result
- **THEN** its source, retrieval time, validity state, and supported claim remain available to downstream consumers (ARD-DAT-004, ARD-DAT-005)

#### Scenario: Partial, stale, or conflicting evidence

- **WHEN** required evidence is missing, stale, or materially conflicting
- **THEN** the system preserves the missing-data or conflict details, labels stale evidence, and does not silently replace uncertainty with a confirmed fact (ARD-DAT-005, ARD-GOV-004, ARD-GOV-005, ARD-RES-006)

### Requirement: Typed agent result and confidence contract

The system MUST validate agent results against a versioned common envelope containing agent identity, status, summary, normalized confidence, assumptions, evidence references, and a role-specific payload. The shared contract MUST NOT prescribe specialist reasoning or imply that an agent result is an approval.

#### Scenario: Valid agent result

- **WHEN** a result contains a supported schema version, valid common fields, confidence from 0.0 through 1.0, and a role-specific payload
- **THEN** the system accepts the typed result without interpreting the specialist's domain decision (ARD-DAT-001, ARD-DAT-006, ARD-DAT-010, ARD-CTL-006)

#### Scenario: Confidence requires provisional handling

- **WHEN** a validated result has confidence from 0.50 through 0.69
- **THEN** it is marked provisional and remains subject to human review before action (ARD-DAT-006, ARD-GOV-002)

#### Scenario: Confidence requires escalation

- **WHEN** a validated result has confidence below 0.50 or material evidence conflicts
- **THEN** the system marks escalation or adjudication as required regardless of any higher aggregate confidence (ARD-GOV-003, ARD-GOV-004)

### Requirement: Deterministic boundary validation

The system MUST deterministically validate required fields, supported schema versions, field constraints, evidence references, and confidence ranges at shared boundaries. Validation failures MUST identify errors and MUST NOT be converted into business defaults or success-shaped results.

#### Scenario: Reproducible validation

- **WHEN** identical inputs are validated under the same configured rules
- **THEN** validation produces the same result and field-level findings (ARD-DAT-009, ARD-NFR-003, ARD-TST-002)

#### Scenario: Unsupported version or malformed output

- **WHEN** a boundary receives an unsupported version or malformed data
- **THEN** it rejects the data with a structured validation failure and does not silently coerce it into a valid business result (ARD-DAT-008, ARD-DAT-009, ARD-DAT-010)

### Requirement: Explicit tool result contract

Every tool request and result MUST be typed and versioned, identify case and correlation context, and expose outcome status, source, timestamp, warnings, returned data on success, or a structured error on failure.

#### Scenario: Successful tool result

- **WHEN** a tool returns valid data
- **THEN** its result identifies success, source, timestamp, correlation context, warnings, and validated data (ARD-DAT-003, ARD-DAT-007, ARD-DAT-010)

#### Scenario: Tool failure or malformed response

- **WHEN** a tool is unavailable, times out, or returns malformed data
- **THEN** the system emits an explicit structured failure with category and impact, preserves any degradation warning, and does not return a success-shaped fallback (ARD-DAT-008, ARD-RES-002, ARD-RES-003, ARD-RES-006)

### Requirement: Read-only adapter boundary

Enterprise data access MUST occur through typed, allowlisted adapter or tool contracts that default to read-only behavior. Local or mock adapters MUST be deterministic, and adapter unavailability MUST be represented explicitly without requiring a live enterprise service.

#### Scenario: Deterministic local adapter

- **WHEN** a shared tool contract is exercised with a local or mock adapter
- **THEN** identical requests produce reproducible contract-conforming results without live enterprise connectivity (ARD-SYS-007, ARD-SYS-008, ARD-NFR-003, ARD-NFR-005)

#### Scenario: Write operation is not enabled

- **WHEN** a caller attempts an operational write through a foundation adapter
- **THEN** the request is unavailable or rejected because the foundation exposes no operational write capability (ARD-SEC-001, ARD-SEC-002, ARD-SEC-003, ARD-GOV-008)

### Requirement: Human approval is a separate decision

The system MUST represent human approval, rejection, escalation, or request for more information separately from agent and tool outputs. An approval record MUST include case ID, selected action and option when applicable, reviewer identity or test identity, timestamp, rationale, and recommendation version; applicable operational and airworthiness approvals MUST remain attributable to their authorized human roles.

#### Scenario: Agent result cannot approve action

- **WHEN** an agent result or confidence value is received without a human decision record
- **THEN** the case remains unapproved and no operational action is performed (ARD-GOV-001, ARD-GOV-002, ARD-GOV-008, ARD-TST-005)

#### Scenario: Approval is recorded

- **WHEN** an authorized human records a decision on a recommendation
- **THEN** the system stores the required decision fields and binds the record to the reviewed recommendation version (ARD-GOV-006, ARD-GOV-007, ARD-SEC-009)

#### Scenario: Repair or part decision requires both authorities

- **WHEN** a recovery plan includes a repair or part decision
- **THEN** approval is not complete until both the Ops lead and Maintenance/airworthiness authority decisions are recorded (ARD-GOV-006, ARD-GOV-008)

### Requirement: Correlated structured audit events

The system MUST emit structured events for foundation validation, tool invocation and result, failure or fallback, conflict, escalation, and human decision. Each event MUST include timestamp, event type, case ID, trace or correlation ID, component, status, and schema version, and MUST avoid private chain-of-thought and unnecessary sensitive data.

#### Scenario: Events share case trace context

- **WHEN** a case-related tool call or component execution emits an event
- **THEN** its event includes the case identifier and propagated trace or correlation identifier with the required event metadata (ARD-DAT-003, ARD-OBS-001, ARD-OBS-002, ARD-OBS-003)

#### Scenario: Event contains rationale without private reasoning

- **WHEN** a decision or validation outcome is recorded for audit
- **THEN** the event retains relevant inputs, outputs, evidence references, rule outcomes, and concise rationale without requiring private chain-of-thought (ARD-OBS-003, ARD-OBS-004, ARD-SEC-006, ARD-SEC-007)

### Requirement: Validated externalized configuration

The system MUST load non-secret runtime configuration through typed settings, keep secret values out of source files and logs, and reject invalid timeout, adapter-selection, or policy-threshold configuration instead of silently substituting operational defaults.

#### Scenario: Valid environment configuration

- **WHEN** supported environment configuration supplies valid settings and secret references
- **THEN** the system loads typed settings without exposing secret values in output or logs (ARD-TEC-004, ARD-SEC-006, ARD-SEC-007, ARD-NFR-006)

#### Scenario: Invalid configuration

- **WHEN** timeout or other constrained settings are invalid
- **THEN** startup or configuration loading fails with an explicit validation error and does not silently select a different adapter or policy (ARD-DAT-009, ARD-NFR-001, ARD-NFR-006)