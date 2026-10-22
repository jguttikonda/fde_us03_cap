# Spec Delta

## ADDED Requirements

### Requirement: Controller ADK Web runs complete synthetic recovery scenarios
The ADK Web demonstration MUST run named synthetic AOG cases through the complete Controller decision workflow and present the deterministic report, evidence references, confidence, compliance exclusions, conflicts, and human-gate state. Enterprise case data MUST remain synthetic/local, and no operational action may be executed. (ARD-TEC-002/005, ARD-CTL-001..019, ARD-DEP-006, ARD-RUB-010, ARD-TST-001/006/009)

#### Scenario: Happy-path repair is available in ADK Web
- **WHEN** a presenter selects the complete repair scenario in the ADK Web interface
- **THEN** the result shows the Controller's source-backed repair option, evidence-linked trade-offs, confidence and score, and a pending human gate (ARD-CTL-013..016, ARD-GOV-001/006..008)

#### Scenario: Degraded inventory remains visible in ADK Web
- **WHEN** a presenter selects the unavailable-inventory scenario
- **THEN** the result preserves the primary source failure, labels cached evidence with its retrieval time and stale validity, lowers confidence, and keeps approval pending or escalated (ARD-RES-001/006, ARD-MLG-007, ARD-GOV-004..005)

#### Scenario: Conflicting estimates require human adjudication
- **WHEN** a presenter selects the Maintenance three-hour versus Operations seven-hour scenario
- **THEN** both source-backed estimates and their conflict remain visible, and the recommendation is provisional or escalated with approval deferred (ARD-GOV-004, ARD-TST-006)

#### Scenario: Close scores require explicit human choice
- **WHEN** the synthetic scenario produces eligible options within the inclusive two-point threshold
- **THEN** both options and their trade-offs are shown, the UI requests human selection, and no option is approved or executed (ARD-CTL-015..016, ARD-GOV-006..008)

#### Scenario: Demo requests do not access operational systems
- **WHEN** any named synthetic scenario is run through ADK Web
- **THEN** only deterministic local/mock enterprise adapters are used; no live airline data is sent to the model and no purchase, transfer, shipment, booking, dispatch, delay, aircraft assignment, or other operational write is performed (ARD-SEC-001..003/008, ARD-PRN-001..002, ARD-TST-009)

#### Scenario: An unknown scenario is not fabricated
- **WHEN** a presenter requests a scenario name not in the supported demo set
- **THEN** the UI identifies the invalid name and lists supported scenarios without constructing a synthetic success result (ARD-DAT-008..010, ARD-RES-006)

#### Scenario: Model credential is missing or remains a template
- **WHEN** ADK Web startup requires a model credential that is absent or still an example placeholder
- **THEN** startup fails with a safe configuration error that does not expose or substitute a credential and does not present the demo as ready (ARD-DEP-001..002, ARD-SEC-006)
