# capstone-demonstration Specification

## Purpose

Defines sponsor-facing demonstration evidence that explains AOG recovery value, evidence-based trade-offs, degraded operation, and human accountability in a concise and reproducible presentation.

## Requirements

### Requirement: Sponsor demonstration is bounded and reproducible
The demonstration package MUST support a sponsor-oriented presentation of no more than ten minutes using deterministic synthetic cases and expected outputs, without live enterprise data or operational writes. (ARD-DEP-006, ARD-RUB-010, ARD-TST-009)

#### Scenario: Happy-path recovery is demonstrated
- **WHEN** the presenter runs the complete synthetic case with source-backed repair, material, and Operations findings
- **THEN** the report communicates business impact, evidence-linked trade-offs, confidence, exclusions, and the required human review (ARD-DEP-006, ARD-CTL-013..016)

#### Scenario: Degraded evidence is demonstrated
- **WHEN** the presenter uses the unavailable-inventory case with explicitly labeled cache or the conflicting three-hour versus seven-hour estimates
- **THEN** the report shows the warning, evidence age or conflict, confidence disposition, and approval deferral without presenting degradation as success (ARD-RES-001/006, ARD-GOV-004..005, ARD-DEP-006)

#### Scenario: Close-score human choice is demonstrated
- **WHEN** two eligible options are within 2 percentage points
- **THEN** the report presents both with their trade-offs and visibly requests human selection without choosing or executing an option (ARD-CTL-015..016, ARD-GOV-006..008)

### Requirement: Demonstration materials explain limits and invite live review
The runbook MUST provide audience-appropriate scenario inputs, expected outputs, timing, business rationale, design choices, risks, caveats, future improvements, and debrief prompts without claiming human review or sponsor acceptance. (ARD-RUB-010..011, ARD-TEC-020)

#### Scenario: Demonstration materials are reviewed before presentation
- **WHEN** the team prepares the sponsor presentation from the runbook
- **THEN** each claimed outcome links to retained evidence, limitations and human approval are explicit, and the team remains responsible for live questions and decisions (ARD-RUB-010..011, ARD-TEC-019..020)
