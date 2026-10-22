## ADDED Requirements

### Requirement: Operations read-only tool identifiers and allowlist

The shared tool contract MUST identify the operations read tools for flight schedule, fleet availability, package load, and alternate flights, in addition to the existing operations status tool, and MUST allowlist them for the Operations and Controller roles only. Specialist roles outside that allowlist MUST receive a structured role-not-allowlisted failure, and no operations tool identifier MAY imply a write capability.

#### Scenario: Operations role reads an operations tool

- **WHEN** the Operations role requests the flight schedule, fleet availability, package load, alternate flights, or operations status tool with read access
- **THEN** the local adapter returns the deterministic fixture result for that tool (ARD-SEC-001, ARD-SEC-003, ARD-SYS-007, ARD-SYS-008)

#### Scenario: Other specialist requests an operations tool

- **WHEN** the Maintenance or Materials & Logistics role requests an operations tool
- **THEN** the adapter returns a structured role-not-allowlisted failure with no data (ARD-SEC-003, ARD-TST-007)
