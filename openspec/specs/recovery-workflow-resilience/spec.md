# recovery-workflow-resilience Specification

## Purpose

Defines reproducible end-to-end evidence that AOG recovery workflows preserve supported findings, uncertainty, and human decision requirements across normal and degraded cases.

## Requirements

### Requirement: End-to-end scenarios preserve the recovery decision contract
The readiness suite MUST exercise the proposal's functional cases through the Controller report boundary using deterministic synthetic inputs and assert observable evidence, eligibility, ranking, and human-gate outcomes. Component-only tests do not satisfy end-to-end coverage. (ARD-TST-001/006/008..009)

#### Scenario: Complete repair evidence supports an advisory repair option
- **WHEN** a part and technician are available and no schedule conflict exists
- **THEN** the report presents a source-backed repair option for human review and performs no operational action (ARD-TST-006)

#### Scenario: Part is unavailable and a substitute aircraft is feasible
- **WHEN** the required part is unavailable and a compatible alternate aircraft is available
- **THEN** the report retains the part constraint and presents the swap candidate with its operational evidence (ARD-TST-006, ARD-OPS-001..004)

#### Scenario: Close scores require human selection
- **WHEN** the top eligible scores differ by no more than 2 percentage points, including exactly 2 points
- **THEN** the report presents the close-score group and trade-offs, requires human selection, and does not declare a unique winner (ARD-CTL-015, ARD-TST-004)

#### Scenario: Maintenance and Materials & Logistics exchange preferred-part evidence
- **WHEN** synthetic history shows three P-110 failures in 90 days and engineering evidence prefers P-120
- **THEN** the H3/H4 exchange is recorded in case context and the report compares source-backed availability, timing, and trade-offs for both paths (ARD-SYS-004, ARD-MNT-009..010, ARD-MLG-009)

#### Scenario: Package redistribution respects capacity and cut-off
- **WHEN** a flight carries 1,200 packages including 700 priority, and a spare aircraft has 900 places before the 17:30 cut-off with no other capacity
- **THEN** priority packages are allocated first, 300 standard packages remain unprotected, and the report includes the unprotected impact and supported cost (ARD-OPS-009, ARD-CTL-019)

#### Scenario: Noncompliant option is excluded before ranking
- **WHEN** P-120 lacks authorization or traceability, or a repair lacks engineering approval
- **THEN** the report identifies the exclusion reason and evidence and assigns the option no score or rank (ARD-CTL-017, ARD-TST-004/006)

#### Scenario: Cost and speed trade off under fixed weights
- **WHEN** compliant candidates trade lower USD cost against slower recovery
- **THEN** the deterministic 30/30/30/10 score determines ordering and exposes factor values and the cost trade-off (ARD-CTL-011..014/019, ARD-TST-004)

### Requirement: Unavailable inventory uses only explicitly degraded cached evidence
When an inventory source is unavailable, the workflow MAY use a cached record only when its provenance and retrieval time are available; cached use MUST remain visibly stale or degraded and MUST lower confidence. (ARD-RES-001/006, ARD-MLG-007, ARD-DAT-004..006)

#### Scenario: Usable cached inventory supports a risk-adjusted result
- **WHEN** the live inventory source is unavailable and a provenance-bearing cached record exists
- **THEN** the result, report, and audit identify cache use, preserve its original retrieval time and stale validity, include a warning, and show lower confidence than the equivalent current-data result (ARD-TST-006)

#### Scenario: Inventory is unavailable without usable cache
- **WHEN** the live source is unavailable and no usable cached record exists
- **THEN** the affected material analysis remains a structured failure or partial result, missing evidence is named, and no success-shaped sourcing path is reported (ARD-RES-001/003..004/006)

### Requirement: Tool and contract failures remain visible end to end
The readiness suite MUST verify that invalid schemas, unavailable tools, and timeouts preserve structured failures, missing analysis, and case impact rather than producing complete-looking reports. (ARD-DAT-008..010, ARD-RES-002..006, ARD-TST-002..003/009)

#### Scenario: Invalid contract data is rejected
- **WHEN** intake, specialist output, or a tool response has a missing required field, unsupported version, or invalid value
- **THEN** validation identifies the affected field or boundary and the Controller does not treat the result as complete (ARD-TST-002)

#### Scenario: Required tool is unavailable or times out
- **WHEN** a required specialist or tool is unavailable or exceeds its configured deadline
- **THEN** the report names the missing analysis, retains a correlated structured failure and warning, and lowers confidence or escalates without erasing other candidate results (ARD-RES-002..004/007)

#### Scenario: Maintenance and Operations estimates materially conflict
- **WHEN** Maintenance estimates three hours and Operations reports the earliest feasible departure is seven hours away
- **THEN** both estimates and evidence remain visible, the result is provisional or escalation-required, and approval is deferred for human adjudication regardless of confidence (ARD-GOV-004, ARD-TST-006)
