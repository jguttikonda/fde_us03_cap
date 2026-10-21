# operations-impact-analysis Specification

## Purpose
TBD - created by archiving change implement-operations-impact-analysis. Update Purpose after archive.
## Requirements
### Requirement: Per-candidate operations request and evaluation

The Operations Agent MUST evaluate each candidate recovery option supplied in a validated, versioned request containing the AOG case, the affected flights, an evaluation time, and for each candidate its identifier, option kind (repair with original part, repair with preferred or alternate part, aircraft swap, or flight delay), and for repair and delay candidates the readiness ETA with its basis from Maintenance and Materials & Logistics. A required input that is absent MUST be reported in a missing-data list and MUST NOT be replaced by an unstated assumption or invented ETA.

#### Scenario: Every supplied candidate is evaluated

- **WHEN** a request contains a repair-with-original-part, a repair-with-alternate-part, a swap, and a delay candidate with a supplied ETA where required
- **THEN** the result contains one recovery option assessment per candidate identifier with its own impact, package outcome, and cost (ARD-OPS-004, ARD-CTL-018)

#### Scenario: Readiness ETA is missing for a repair or delay candidate

- **WHEN** a repair or delay candidate has no readiness ETA
- **THEN** that candidate is reported as undetermined with the missing input named, no ETA is assumed, the result is not complete, and confidence reflects the gap (ARD-GOV-005, ARD-PRN-005, ARD-OPS-006)

#### Scenario: Unsupported request version or unknown field

- **WHEN** a request payload has an unsupported schema version, an unknown field, or an invalid field
- **THEN** boundary validation returns explicit field-level findings and no assessment is produced from it (ARD-DAT-009, ARD-DAT-010, ARD-SEC-004)

### Requirement: Deterministic schedule validation and conflict detection

The system MUST deterministically validate flight and schedule data and detect route and assignment conflicts without model judgment. A conflict MUST identify the affected resources (flights, aircraft, and crew) and the preferred option's viability relative to alternatives.

#### Scenario: Affected flight is validated against the schedule

- **WHEN** the schedule source returns the affected flights with consistent assignments and times
- **THEN** each flight is recorded as validated with its route, scheduled departure, and assigned aircraft, and missing flights are listed as missing data (ARD-OPS-001, ARD-OPS-002)

#### Scenario: Swap aircraft is double-booked or crew coverage is missing

- **WHEN** a swap candidate aircraft has an overlapping assignment or the crew coverage is a gap
- **THEN** the system reports a route or assignment conflict naming the affected aircraft, flights, and crew, and the swap option is marked not viable without hiding the conflict (ARD-OPS-002, ARD-OPS-008)

### Requirement: Fleet substitution evaluation

The system MUST deterministically select substitute-aircraft candidates that are serviceable, of a compatible type, positioned within the configured positioning limit, and available within the swap window, using a deterministic ordering (earliest availability, then larger package capacity, then aircraft identifier).

#### Scenario: Swap aircraft is available

- **WHEN** at least one serviceable compatible aircraft is available within the swap window
- **THEN** the swap candidate uses the first aircraft in the deterministic order and records its tail, availability, and capacity (ARD-OPS-001, ARD-OPS-002, ARD-OPS-004, ARD-NFR-003)

#### Scenario: No swap aircraft is available

- **WHEN** no aircraft satisfies the substitution rules
- **THEN** the swap candidate is reported as not viable with the reason and no substitute is fabricated (ARD-OPS-004, ARD-PRN-005)

### Requirement: Configured disruption impact classification

The system MUST classify operational impact as low, medium, high, or critical using externally configured delay thresholds, raising the level by one step (not above critical) when an affected flight is service-critical or time-critical packages remain unprotected. Given identical inputs and settings the classification MUST be identical.

#### Scenario: Threshold boundaries

- **WHEN** the schedule delay equals each configured threshold boundary
- **THEN** the classification is the exact level configured for that boundary and one minute below the boundary yields the lower level (ARD-OPS-003, ARD-NFR-003, ARD-NFR-006)

#### Scenario: Service-critical uplift

- **WHEN** a seven-hour delay affects a service-critical flight
- **THEN** the classification is critical and the applied rule is recorded (ARD-OPS-003)

### Requirement: Package load redistribution

The system MUST evaluate redistribution of packages from affected flights to the swap aircraft or to other flights, within aircraft capacity by tail, service level, and sort and cut-off windows, using manifest and capacity data. Packages MUST be allocated in deterministic service-level priority order. Packages that cannot be protected MUST be reported as unprotected and included in the option's impact and cost.

#### Scenario: Capacity-limited redistribution with unprotected remainder

- **WHEN** an affected flight carries 1,200 packages of which 700 are priority, a spare aircraft has capacity for 900 and is ready before the 17:30 cut-off, and no other capacity exists
- **THEN** all 700 priority packages and 200 standard packages are redistributed, 300 standard packages are reported as unprotected, and the unprotected count appears in the option impact and cost (ARD-OPS-009, ARD-OPS-005, Proposal test case 6)

#### Scenario: Target misses the cut-off

- **WHEN** a target aircraft or flight cannot depart before a package group's cut-off
- **THEN** that group is not allocated to that target and is reported as unprotected if no other target qualifies (ARD-OPS-009)

#### Scenario: Package data is unavailable

- **WHEN** the package load source fails or returns no manifest for an affected flight
- **THEN** package impact is reported as not assessed, listed as missing analysis, and no package count is assumed (ARD-OPS-009, ARD-GOV-005, ARD-RES-004)

### Requirement: Operational cost component

The system MUST compute for each candidate an estimated operational cost in USD from externally configured mock rates, composed of delay cost, swap cost, rerouting cost on own-network and partner flights, and unprotected package cost, with the components retained in the result. The Operations cost MUST NOT include repair labor or part sourcing cost.

#### Scenario: Cost components sum to the estimate

- **WHEN** a candidate has delay minutes, a swap, rerouted packages, and unprotected packages
- **THEN** the estimate equals the sum of the delay, swap, rerouting, and unprotected-package components using the configured rates (ARD-CTL-019, ARD-OPS-009)

### Requirement: Own-network and partner flight sourcing for package rerouting

The system MUST search own-network and partner flights on each affected route and MUST report every flight found with its carrier type, departure, spare capacity, cost per package, accepted service levels, booking deadline, and whether it is usable and, if not, why. A flight MUST NOT be used when it is a partner flight the request's reroute policy forbids, a partner flight above the policy cost cap, already departed, past its booking deadline, without spare capacity, not accepting the package service level, on a different route, or departing after the package group's cut-off. Own-network flights MUST be used before partner flights when the policy prefers the own network. Rerouting MUST use direct flights only and MUST consume each flight's capacity once. The agent MUST NOT book a flight or move a package; partner use MUST be flagged for human booking.

#### Scenario: Own network first, then partner

- **WHEN** a late repair leaves 1,200 packages without their aircraft before a 17:30 cut-off, with one own flight of 150 capacity and usable partner flights
- **THEN** priority packages fill the own flight first and the remaining partner capacity next, standard-only partner flights take only standard packages, and the remainder is reported unprotected with the rerouting cost (ARD-OPS-009, ARD-CTL-019)

#### Scenario: Policy and usability limits

- **WHEN** the policy forbids partner flights, caps partner cost, or a flight misses its booking deadline or the package cut-off
- **THEN** that flight is listed as not usable with the reason and receives no packages (ARD-OPS-009, ARD-PRN-005)

#### Scenario: Flight search unavailable

- **WHEN** the alternate flight source is unavailable or times out
- **THEN** the result is partial with a warning, the flight search is named as missing analysis, unprotected counts are stated as upper bounds, cost is marked incomplete, and confidence is reduced (ARD-RES-002, ARD-RES-004, ARD-RES-006, ARD-GOV-005)

#### Scenario: Humans book flights

- **WHEN** a result relies on partner flights
- **THEN** the risk factors and next steps state that humans must book them before the deadlines and the agent books nothing (ARD-PRN-001, ARD-GOV-008)

### Requirement: Time-sensitive and incomplete data handling

The system MUST mark an Operations result provisional or partial when operational data is incomplete, stale beyond the configured maximum age, or reported as partial by its source, MUST label stale evidence with its source and retrieval time, and MUST lower confidence by the configured policy.

#### Scenario: Schedule data is stale

- **WHEN** the schedule evidence is older than the configured maximum age relative to the evaluation time
- **THEN** the evidence is labelled stale, the result is partial, confidence is reduced, and the staleness is visible in warnings and the audit trail (ARD-OPS-006, ARD-RES-006, ARD-DAT-005)

#### Scenario: Source returns partial data

- **WHEN** a source reports partial data
- **THEN** the affected conclusions are stated as not fully supported and the result is not complete (ARD-OPS-006, ARD-RES-004)

### Requirement: Timeout and unavailable-source handling

A failed, unavailable, or timed-out operations source MUST be recorded as a structured failure with component, error category, retryability, and case impact. Retries MUST be bounded, MUST reuse the same request identifier, and MUST NOT erase the original failure. The result MUST include a warning, name the missing analysis, and apply the confidence and escalation policy. No source failure MAY produce a success-shaped result.

#### Scenario: Package load source times out

- **WHEN** the package load source times out on every bounded attempt
- **THEN** the result is partial with a warning, package impact is named as missing analysis, a structured timeout failure is retained, and confidence is reduced (ARD-RES-002, ARD-RES-003, ARD-RES-005, ARD-RES-006)

#### Scenario: Essential schedule source is unavailable

- **WHEN** the flight schedule source is unavailable
- **THEN** the result status is failed with a structured error and zero confidence, no recovery option is assessed, and escalation is indicated (ARD-RES-003, ARD-GOV-003)

#### Scenario: Retry is bounded and idempotent

- **WHEN** a retryable failure occurs
- **THEN** at most the configured number of retries is made, each with the original request identifier (ARD-RES-005, ARD-NFR-002)

### Requirement: Conflicting time estimates and material customer trade-offs

The system MUST report a conflict when the operationally feasible departure for a candidate differs from the supplied Maintenance or Materials & Logistics ETA by more than the configured conflict threshold, preserving both estimates and their evidence references. A conflict MUST make the result escalation-required and defer approval regardless of numeric confidence. When more than one operationally viable candidate has materially different customer or package impact, the alternatives and trade-offs MUST be presented for human selection.

#### Scenario: Maintenance and Operations estimates conflict

- **WHEN** Maintenance supplies a three-hour ETA and crew availability makes the earliest feasible departure seven hours out
- **THEN** a conflict records both estimates and references, the status is escalation-required, and human adjudication is required (ARD-GOV-004, Proposal scenario: Conflicting Data)

#### Scenario: Viable options differ materially in customer impact

- **WHEN** two viable candidates differ in unprotected packages or impact level beyond the configured materiality limits
- **THEN** both are reported with their trade-offs and the result requires human selection, with no candidate ranked (ARD-OPS-007, ARD-CTL-015)

### Requirement: Structured operations result and confidence

The system MUST return the shared agent-result envelope with an Operations payload containing affected routes, impact level, per-candidate recovery options with impact estimates and cost, package impact, risk factors, assumptions, missing data, conflicts, warnings, a recommendation limited to the evaluated candidate's operational viability, confidence, reasoning, and next steps. Confidence MUST be computed by deterministic policy and classified by the shared thresholds. The result MUST NOT rank options, approve a plan, or claim safety or airworthiness.

#### Scenario: Normal evidence

- **WHEN** all sources are current and complete with no conflict
- **THEN** the result status is complete, confidence is at least 0.70, the disposition is preferred, and human approval is still required (ARD-OPS-005, ARD-GOV-001, ARD-GOV-008)

#### Scenario: Provisional confidence

- **WHEN** confidence is from 0.50 through 0.69
- **THEN** the result is marked provisional and requires human review before action (ARD-GOV-002, ARD-OPS-006)

#### Scenario: Low confidence

- **WHEN** confidence is below 0.50
- **THEN** the result requires escalation for additional data or explicit human override (ARD-GOV-003)

#### Scenario: Evidence references resolve

- **WHEN** the result is validated against the evidence produced for the case
- **THEN** every evidence reference and assumption reference resolves and the envelope passes shared agent-result validation (ARD-CTL-006, ARD-DAT-004)

### Requirement: Bounded reasoning with deterministic guardrails

The system MUST confine model judgment to explanation and trade-off narrative over deterministic facts, accessed only through Google ADK-governed interfaces, and MUST validate the reasoning output before it is returned. Reasoning that alters computed values, claims safety or airworthiness, implies approval or execution, or is empty MUST be rejected, the rejection MUST be visible as a warning, and the deterministic summary MUST be used with its source labelled.

#### Scenario: Reasoning is accepted

- **WHEN** the reasoner returns a non-empty explanation consistent with the computed facts
- **THEN** it is included in the result with the reasoner mode labelled (ARD-PRN-003, ARD-PRN-004, ARD-OPS-005)

#### Scenario: Reasoning claims airworthiness or approval

- **WHEN** the reasoner output states the aircraft is safe or airworthy, or that a plan is approved or executed
- **THEN** the guardrail rejects it, a warning names the rejection, and the deterministic narrative is used (ARD-SEC-008, ARD-GOV-008, ARD-RES-006)

#### Scenario: ADK agent definition and no model call in tests

- **WHEN** the ADK agent definition is built
- **THEN** it is a Google ADK `LlmAgent` carrying the grounding, trade-off, and validation prompts and only read-only allowlisted tools, and no test invokes a model or network (ARD-TEC-002, ARD-TEC-005, ARD-TST-009)

### Requirement: Untrusted tool data and read-only allowlisted access

Operations tool responses MUST be validated as untrusted input; invalid or unknown-field data MUST become a structured malformed-data failure. Free text from tools MUST NOT be passed to the reasoner, change policy, authorize tools, or alter the agent's role. The Operations Agent MUST use only read-only operations tools it is allowlisted for and MUST NOT perform any operational action.

#### Scenario: Malformed source data

- **WHEN** a source returns data that fails validation
- **THEN** the source is recorded as a structured malformed-data failure and its data is not used (ARD-SEC-004, ARD-DAT-008, ARD-TST-007)

#### Scenario: Prompt-injection text in tool data

- **WHEN** a disruption description contains instructions to approve a plan or change tool access
- **THEN** the text is not used in reasoning or output, the assessment values are unchanged, and no approval, execution, or tool-scope change occurs (ARD-SEC-005, ARD-TST-007)

#### Scenario: Role not allowlisted

- **WHEN** a non-Operations specialist role requests an operations-only tool
- **THEN** the adapter returns a structured role-not-allowlisted failure and no data (ARD-SEC-001, ARD-SEC-003, ARD-TST-007)

#### Scenario: Advisory-only boundary

- **WHEN** any result is produced, including high-confidence, degraded, or test-mode results
- **THEN** the payload states advisory-only and human approval required, and no write capability exists in the agent or its tools (ARD-PRN-001, ARD-PRN-002, ARD-GOV-008, ARD-SEC-002, ARD-TST-005)

### Requirement: Correlated audit events and case isolation

The system MUST emit structured, redacted, correlated audit events for operations intake validation, tool results, fallback or degradation, conflict, escalation, and assessment completion, containing timestamp, event type, case identifier, trace and correlation identifiers, component, status, and schema version, and concise rationale without private reasoning. A failure in one case MUST NOT affect another case's results.

#### Scenario: Events carry required metadata

- **WHEN** an assessment runs
- **THEN** each emitted event carries the required fields, evidence references, and concise rationale (ARD-OBS-001, ARD-OBS-002, ARD-OBS-004, ARD-SEC-007)

#### Scenario: Case isolation

- **WHEN** two cases are assessed and one source fails for one case
- **THEN** the other case's result, evidence, and events are unaffected (ARD-RES-007)

### Requirement: Reserved flight capacity

The system MUST exclude from rerouting any package capacity that the request reports as already reserved on an alternate flight by another recovery action, MUST list a flight whose capacity is fully reserved as not usable with that reason, and MUST record the exclusion as an assumption. Reservations are supplied by the Controller; the agent MUST NOT create, change, or release them.

#### Scenario: Capacity reserved by another action

- **WHEN** an own-network flight has 150 spare packages and 150 are reserved by a Materials & Logistics shipment
- **THEN** the flight is not usable, packages go to other usable flights or are reported unprotected, and the assumptions name the reserved capacity (ARD-OPS-009, ARD-RES-006)

#### Scenario: Partial reservation

- **WHEN** 100 of 150 spare packages are reserved
- **THEN** only 50 are offered for rerouting (ARD-OPS-009)

