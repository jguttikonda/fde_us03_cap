# Spec Delta

## Purpose

Defines how the Controller turns validated, per-candidate specialist findings into a deterministic, evidence-backed AOG recovery brief and records human decisions without executing operational actions.

## ADDED Requirements

### Requirement: Candidate evaluations feed one Controller-owned recommendation
The Controller MUST consume candidate-specific Maintenance, Materials & Logistics, and Operations findings for original-part repair, preferred or alternate-part repair, aircraft swap, and flight delay. Maintenance and Materials & Logistics evaluations MUST run concurrently per candidate, followed by Operations evaluation using that candidate's readiness ETA. The Controller alone owns workflow completion, ranking, explanation, and report generation. (ARD-SYS-002/005, ARD-CTL-009/010/018)

#### Scenario: Candidate set is evaluated and carried into the brief
- **WHEN** validated case evidence supports multiple recovery candidates
- **THEN** the Controller preserves each candidate's sourcing method, readiness, load-redistribution findings, evidence, and specialist result in its recommendation inputs (ARD-CTL-018, ARD-DAT-004)

### Requirement: Compliance eligibility precedes scoring
The Controller MUST apply the compliance gate before scoring. Any candidate that fails or lacks required engineering approval, part authorization, compatibility, or traceability MUST be listed with its reason and MUST NOT receive a score or rank. (ARD-CTL-017, ARD-GOV-005)

#### Scenario: Noncompliant candidate is excluded
- **WHEN** a candidate fails or lacks a required approval or part-eligibility record
- **THEN** the report lists the candidate and specific exclusion reason, and contains no score or rank for it (ARD-CTL-017)

#### Scenario: Eligible candidate proceeds to scoring
- **WHEN** a candidate has the required current approval and part-eligibility evidence
- **THEN** it proceeds to deterministic scoring only after the compliance gate completes (ARD-CTL-011/017)

### Requirement: Eligible candidates receive deterministic weighted scores
The Controller MUST score each eligible, scoreable candidate with fixed normalization and the baseline weights of speed 30%, operational and package impact 30%, risk 30%, and total estimated cost 10%. The total estimated cost MUST be expressed in USD and account for repair labor, part/sourcing/transfer/expedite, and delay/swap costs. (ARD-CTL-011..012/019)

#### Scenario: Complete candidates receive reproducible scores
- **WHEN** the same complete candidate evidence is evaluated repeatedly
- **THEN** the Controller returns the same factor scores, weights, aggregate scores, and relative ordering, with the 30/30/30/10 weights visible (ARD-CTL-011..012)

#### Scenario: Score factors and cost affect ordering
- **WHEN** two compliant candidates trade recovery speed against operational impact, risk, or total cost
- **THEN** the Controller ranks them by the weighted aggregate and reports each factor score and total USD cost so the trade-off can be checked (ARD-CTL-011..014/019)

### Requirement: Decision brief explains evidence and uncertainty
The Controller MUST produce a versioned brief with status, ranked alternatives, scores, evidence references, trade-offs, risks, warnings, confidence, and required human action. Missing, stale, conflicting, or unavailable evidence MUST remain visible and MUST NOT be replaced by assumptions or success-shaped fallbacks. (ARD-CTL-013..014/016, ARD-DAT-004..006, ARD-GOV-004..005, ARD-RES-001..006)

#### Scenario: Report shows source-backed trade-offs
- **WHEN** candidates have complete validated findings
- **THEN** the summary identifies the leading option and its material trade-off, while the brief links score rationale to available evidence, assumptions, and risks (ARD-CTL-013..016, ARD-PRN-005)

#### Scenario: Partial or unavailable evidence remains visible
- **WHEN** required findings, cost components, or source data are missing, stale, failed, or conflicting
- **THEN** the brief names the affected candidate and missing or degraded evidence, lowers confidence or escalates, and does not invent a score input (ARD-CTL-008/016, ARD-GOV-004..005, ARD-RES-001..006)

### Requirement: Close scores and confidence determine recommendation posture
The Controller MUST present top candidates within 2 percentage points together for human selection. Confidence of at least 0.70 MAY identify a preferred path but MUST remain pending approval; confidence from 0.50 through 0.69 MUST be provisional; confidence below 0.50 or material conflict MUST require escalation and defer approval. (ARD-CTL-015..016, ARD-GOV-001..004/008)

#### Scenario: Close scores require human selection
- **WHEN** the top eligible candidates are within 2 percentage points
- **THEN** the brief summary names the close-score group, presents both with their trade-offs, and requires the human to select without declaring a unique winner (ARD-CTL-015)

#### Scenario: Provisional, low-confidence, or conflicting findings
- **WHEN** confidence is provisional, below threshold, or material evidence conflicts
- **THEN** the report labels the disposition as provisional or escalation-required, shows the evidence gap or conflict, and keeps approval deferred (ARD-GOV-002..004/008)

#### Scenario: No scoreable option exists
- **WHEN** no candidate passes compliance or has sufficient evidence for a defensible score
- **THEN** the Controller returns exclusions and/or missing-data reasons with an escalation or awaiting-additional-data status, keeps approval pending, and fabricates no preferred option (ARD-CTL-010/016..017, ARD-GOV-003..005)

### Requirement: Human decision is versioned, auditable, and separate from recommendation
The system MUST support human approve, reject, escalate, and request-more-information decisions. Approval MUST require both approver roles to agree on the same case, option, and recommendation version. Each record MUST include case, action, option when applicable, reviewer identity and role, timestamp, rationale, and version. No agent or score may approve or execute an operational action. (ARD-SYS-006, ARD-GOV-006..008, ARD-PRN-001..002/008)

#### Scenario: Both required roles approve the same recommendation
- **WHEN** the Ops lead and Maintenance/airworthiness authority approve the same option and active recommendation version
- **THEN** the report records both reviewers' identities, roles, timestamps, and rationales against the case, option, and version, sets the terminal status to resolved, and performs no operational action (ARD-CTL-010, ARD-GOV-006..008)

#### Scenario: Approval is partial, stale, or inconsistent
- **WHEN** an approval is missing a required reviewer, refers to another option or case, or uses a stale recommendation version
- **THEN** approval remains pending and the mismatch is recorded for review (ARD-GOV-006..008)

#### Scenario: Human rejects, escalates, or requests information
- **WHEN** an authorized human records reject, escalate, or request-more-information
- **THEN** the Controller records the action and rationale against the active recommendation version and updates the workflow status without executing an operational action (ARD-CTL-010, ARD-GOV-006..008)

### Requirement: Recommendation and decision audit trail is reconstructable
The Controller MUST append correlated audit events for recommendation generation, scoring, exclusion, escalation, and each human decision. Events MUST identify the case, recommendation version, status, timestamp, and evidence references without storing private chain-of-thought or sensitive data. (ARD-PRN-008, ARD-OBS-001..004, ARD-SEC-007/009)

#### Scenario: Recommendation and human decision are linked in audit history
- **WHEN** a recommendation is issued and a human decision is recorded
- **THEN** case-correlated events retain the recommendation version, decision action, reviewer, timestamp, rationale, and relevant evidence references (ARD-GOV-007, ARD-OBS-001..004)

#### Scenario: Audit append fails
- **WHEN** a required recommendation or decision audit append fails
- **THEN** the result reports an explicit incomplete or failed status and does not claim an auditable completed decision (ARD-RES-003..006, ARD-SEC-009)
