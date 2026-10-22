# Spec Delta

## MODIFIED Requirements

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
