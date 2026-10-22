# security-and-audit Specification

## Purpose

Defines cross-component security and audit evidence that makes AOG decision support least-privileged, reviewable, and unable to take operational action.

## Requirements

### Requirement: Readiness verification proves least-privilege tool boundaries
Every agent and adapter MUST be limited to its documented role allowlist and read-only capabilities; the readiness evidence MUST verify denied access as well as successful reads. (ARD-SEC-001..004, ARD-SYS-007..009, ARD-TST-007)

#### Scenario: Unauthorized role or action is rejected
- **WHEN** a role requests a tool outside its allowlist or attempts a purchase, transfer, booking, dispatch, or other operational write
- **THEN** the boundary returns a structured denial with no data or side effect (ARD-SEC-001..003, ARD-GOV-008)

#### Scenario: Tool response contains untrusted instructions
- **WHEN** external text asks an agent to change policy, reveal secrets, or enable a tool
- **THEN** it is treated as untrusted data, does not alter policy or tool access, and does not change deterministic findings (ARD-SEC-004..005, ARD-TST-007)

#### Scenario: External data violates a contract
- **WHEN** a tool returns malformed or unknown-field data
- **THEN** validation rejects it as a structured failure and no unsupported data is used in a recommendation (ARD-DAT-008..010, ARD-SEC-004)

### Requirement: Audit evidence is correlated, redacted, and reconstructable
Readiness evidence MUST verify that externally observable case events preserve the recommendation and evidence version while excluding secrets, unnecessary sensitive data, and private chain-of-thought. (ARD-OBS-001..004, ARD-SEC-006..009, ARD-PRN-008)

#### Scenario: Case trajectory is correlated and redacted
- **WHEN** a workflow records intake, tool use, agent result, fallback, conflict, score, escalation, or human decision
- **THEN** events carry timestamp, event type, case and trace/correlation identifiers, component, status, and schema version; sensitive values are redacted and concise rationale and evidence references remain available (ARD-OBS-001..004, ARD-SEC-006..009)

#### Scenario: Audit persistence fails
- **WHEN** a required case or decision audit append fails
- **THEN** the result reports an incomplete or failed audit state and does not claim a fully reconstructable decision (ARD-RES-003..006, ARD-SEC-009)

### Requirement: Security checks preserve mandatory human authority
Readiness verification MUST establish that agent output, confidence, test configuration, degraded behavior, or audit status cannot approve or execute an operational decision. (ARD-GOV-001..008, ARD-PRN-001..002, ARD-TST-005)

#### Scenario: Confidence or test mode cannot bypass approval
- **WHEN** a recommendation is high-confidence, provisional, low-confidence, conflicted, or produced in a test mode
- **THEN** the human gate remains pending or escalation-required until authorized human decisions match the same case, option, and recommendation version (ARD-GOV-001..008)

#### Scenario: Required approvers disagree
- **WHEN** the Ops lead and Maintenance/airworthiness authority select different options or report versions
- **THEN** approval remains pending and the mismatch is recorded for human review (ARD-GOV-006..008)
