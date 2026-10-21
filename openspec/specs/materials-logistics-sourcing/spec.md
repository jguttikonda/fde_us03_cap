# materials-logistics-sourcing Specification

## Purpose

Defines evidence-grounded part availability and sourcing analysis so Maintenance and the Controller receive realistic, authorized material-readiness options and lead-time estimates.

## Requirements

### Requirement: Material availability reflects practical recovery constraints

The Materials & Logistics result MUST classify availability as available, limited, unavailable, or uncertain and distinguish physical stock from material usable within the recovery window. It MUST consider part number, aircraft compatibility, quantity, station, transfer state, supplier constraints, shipping, lead time, and the case need-by time when available. (ARD-MLG-001, ARD-MLG-003..004)

#### Scenario: Stock is physically present but misses the recovery window

- **WHEN** a source reports stock but transfer or shipping makes it unavailable by the need-by time
- **THEN** the result reports physical stock and practical unavailability separately, with the limiting source evidence and timing constraint (ARD-MLG-004..005, ARD-DAT-004)

#### Scenario: Required availability inputs are missing

- **WHEN** quantity, location, compatibility, or timing evidence needed for availability is missing
- **THEN** the result marks availability uncertain, lists missing data, and does not treat unknown stock as available (ARD-MLG-001, ARD-GOV-005, ARD-RES-004)

### Requirement: Substitute and part authorization checks precede recommendation

An alternate, substitute, or preferred replacement part MUST NOT be presented as eligible unless deterministic compatibility, authorization, and traceability checks succeed. Failed or unknown checks MUST remain explicit in the result. (ARD-MLG-002, ARD-MLG-008, ARD-CTL-017, ARD-SEC-004)

#### Scenario: Approved compatible alternate passes validation

- **WHEN** deterministic compatibility, authorization, and traceability evidence validates an alternate part
- **THEN** the part may be included as an eligible sourcing option with the supporting evidence references (ARD-MLG-008, ARD-DAT-004)

#### Scenario: Compatibility or authorization is missing or rejected

- **WHEN** an alternate part fails compatibility or lacks authorization/traceability evidence
- **THEN** it is not presented as an eligible replacement, and the failed or unknown check is visible with its source (ARD-MLG-008, ARD-CTL-017, ARD-GOV-005)

### Requirement: Original and preferred parts are compared for H4 response

When Maintenance supplies a failed part and a preferred replacement, Materials & Logistics MUST evaluate both parts for availability, lead time, location, and transfer feasibility before returning its comparison. (ARD-MLG-009, ARD-SYS-004)

#### Scenario: Original and preferred replacement can be compared

- **WHEN** the H3 request includes a failed part and an engineering-supported preferred replacement
- **THEN** the H4 response contains separate source-backed availability, location, lead-time, and transfer findings for both parts (ARD-MLG-009, ARD-DAT-004)

#### Scenario: Preferred-part evidence is incomplete

- **WHEN** one of the requested parts has missing, stale, or conflicting source data
- **THEN** the comparison preserves that part's evidence state and returns a partial or uncertain result instead of omitting it or treating it as unavailable by default (ARD-MLG-007, ARD-GOV-004..005, ARD-RES-004, ARD-RES-006)

### Requirement: Sourcing and shipping options include deterministic ETA and mock cost

For each feasible source path, Materials & Logistics MUST report the source, method, transfer requirement, shipping provider/service, parts-ready ETA, transit/lead time, and estimated cost in USD when supported by fixture or validated adapter data. It MUST distinguish internal transfer, borrow/pool, vendor purchase, and expedite paths and FedEx Network priority freight/courier from commercial-carrier options. (ARD-MLG-002, ARD-MLG-005..006, ARD-TEC-008..009)

#### Scenario: Multiple sourcing paths have comparable quotes

- **WHEN** deterministic fixture data supplies valid costs and lead times for multiple sourcing/shipping paths
- **THEN** the result returns each path's cost and ETA separately with its source and assumptions, without ranking recovery options (ARD-MLG-005..006, ARD-SYS-008)

#### Scenario: A quote is incomplete

- **WHEN** a path lacks supported cost or ETA inputs
- **THEN** the corresponding value is marked unavailable or unknown with a warning rather than populated with a business default (ARD-DAT-005, ARD-DAT-009, ARD-GOV-005)

### Requirement: Stale and cached data remain visibly degraded

Cached or stale inventory, supplier, transfer, or shipping data MUST retain its source, retrieval time, and validity state, MUST be labeled in the result, and MUST reduce confidence under a deterministic non-secret policy. (ARD-MLG-007, ARD-RES-001, ARD-RES-006, ARD-DAT-004..006)

#### Scenario: Unavailable source permits labeled cached evidence

- **WHEN** a source is unavailable and a cached record with explicit provenance is available
- **THEN** the result identifies cached use, preserves the original retrieval time and stale state, emits a warning, and reports lower confidence than the equivalent current-data result (ARD-RES-001, ARD-MLG-007, ARD-RES-006)

#### Scenario: No usable cache is available

- **WHEN** a source is unavailable and no usable cached data exists
- **THEN** the result is a structured failure or partial result identifying the unavailable analysis and does not return a success-shaped sourcing path (ARD-RES-001, ARD-RES-003..004, ARD-RES-006)

### Requirement: Materials tools remain read-only and failures explicit

Materials tools MUST be role-allowlisted and read-only. Unavailable, timed-out, malformed, partial, or conflicting responses MUST preserve structured failure/warning information and MUST NOT execute procurement, reservation, transfer, or shipment actions. (ARD-SYS-007..009, ARD-SEC-001..005, ARD-RES-001..006)

#### Scenario: Materials source fails or returns malformed data

- **WHEN** a materials tool is unavailable, times out, or returns invalid data
- **THEN** the caller receives a correlated structured error or partial result with the affected source and impact visible (ARD-DAT-007..009, ARD-RES-003..004, ARD-SEC-004)

#### Scenario: Caller requests an operational materials action

- **WHEN** a caller attempts to purchase, reserve, transfer, borrow, or ship a part through a foundation tool
- **THEN** the request is rejected because the capability exposes no operational write action (ARD-SEC-001..003, ARD-GOV-008)
