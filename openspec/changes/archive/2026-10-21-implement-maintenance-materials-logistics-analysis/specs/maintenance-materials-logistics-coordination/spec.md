# Spec Delta

## Purpose

Defines the traceable Maintenance-to-Materials & Logistics peer exchange needed to compare a failed part with a preferred replacement while leaving workflow ownership with the Controller.

## ADDED Requirements

### Requirement: H3 replacement-strategy request carries maintenance evidence

An H3 request from Maintenance MUST identify the case and exchange, failed part, preferred part when present, aircraft/station context, need-by time, maintenance evidence references, recurring-failure count/window when present, and trace/correlation context. Missing values MUST be explicit rather than inferred. (ARD-SYS-004, ARD-MNT-009, ARD-DAT-003..005, ARD-DAT-010)

#### Scenario: Maintenance requests evaluation of a preferred replacement

- **WHEN** Maintenance has evidence of a failed part, recurring failures, and an engineering-supported preferred replacement
- **THEN** H3 transmits both part identifiers, evidence references, station, need-by time, and matching case/trace identifiers (ARD-MNT-009, ARD-MLG-009, ARD-SYS-004)

#### Scenario: H3 lacks required part or case context

- **WHEN** the request lacks its case, correlation, failed-part, or required source context
- **THEN** it is rejected with field-level findings and no Materials & Logistics conclusion is inferred (ARD-DAT-009, ARD-CTL-006, ARD-GOV-005)

### Requirement: H4 response compares original and preferred replacement

The H4 response MUST correlate to its H3 exchange and return source-backed availability, location, practical lead time, transfer feasibility, sourcing alternatives, and uncertainty for both the failed part and preferred replacement when one is supplied. (ARD-MLG-005..006, ARD-MLG-009, ARD-SYS-004, ARD-DAT-003..007)

#### Scenario: Both parts have current inventory evidence

- **WHEN** source-backed inventory and lead-time records exist for the failed and preferred parts
- **THEN** H4 returns a separate comparison for each part and preserves the source, retrieval time, and claim references (ARD-MLG-009, ARD-DAT-004)

#### Scenario: One part has stale, conflicting, or missing evidence

- **WHEN** evidence for either part is stale, conflicting, partial, or unavailable
- **THEN** H4 labels the affected finding, retains available values and source references, and returns a partial or uncertain response rather than treating the evidence as current (ARD-MLG-007, ARD-GOV-004..005, ARD-RES-003..006)

### Requirement: Every peer exchange is recorded in Controller-managed case context

Each H3 request and H4 response MUST be appended to the matching Controller-managed case context with exchange ID, case/trace/correlation IDs, direction, timestamp, status, and evidence references. The specialists MUST use a recorder boundary and MUST NOT create or own Controller routing or workflow state. (ARD-SYS-002..004, ARD-OBS-001..003, ARD-SEC-009)

#### Scenario: H3 and H4 are both recorded

- **WHEN** the recorder accepts a peer request and its response
- **THEN** both append-only records are retrievable under the same case and exchange IDs in request/response order (ARD-SYS-004, ARD-OBS-002, ARD-SEC-009)

#### Scenario: Case-context recording fails

- **WHEN** the recorder cannot append either side of an exchange
- **THEN** the exchange is marked incomplete with a structured failure and is not reported as a successfully recorded collaboration (ARD-RES-003..006, ARD-OBS-003, ARD-SEC-009)

### Requirement: Peer errors and conflicts remain visible to the Controller

The peer exchange MUST preserve incompatible part, station, authorization, availability, or timing evidence with source references and MUST return structured failure or conflict status for Controller-owned adjudication. Neither specialist may silently select a winner or rank recovery options. (ARD-MNT-008..009, ARD-MLG-009, ARD-CTL-007..008, ARD-GOV-004, ARD-PRN-006)

#### Scenario: Maintenance and supply evidence conflict

- **WHEN** Maintenance's requested part or need-by assumptions conflict with Materials & Logistics source data
- **THEN** both values and provenance are retained, the exchange is marked conflicted or provisional, and the Controller receives the unresolved conflict for adjudication (ARD-MNT-008, ARD-CTL-007, ARD-GOV-004)

#### Scenario: Peer tool or response fails

- **WHEN** a peer response is unavailable, times out, or fails schema validation
- **THEN** the exchange retains a correlated structured failure and the requesting specialist does not substitute a success-shaped result (ARD-DAT-008..010, ARD-RES-003..006, ARD-SEC-004)

### Requirement: Peer exchange has no operational side effects

H3/H4 messages MUST be advisory data requests and results only. Neither peer may purchase, reserve, transfer, borrow, expedite, ship, or modify a work order or aircraft state. (ARD-PRN-001..002, ARD-SYS-006..008, ARD-SEC-001..003, ARD-GOV-008)

#### Scenario: A peer request implies an operational action

- **WHEN** a request asks either specialist to execute sourcing, movement, maintenance, or aircraft operations
- **THEN** the request is rejected or returned as an advisory recommendation with no operational action performed (ARD-PRN-002, ARD-SEC-002..003, ARD-GOV-008)