# Spec Delta

## Purpose

Coordinates validated Maintenance, Materials & Logistics, and Operations findings into an explainable AOG recovery decision brief for human review.

## ADDED Requirements

### Requirement: Validate AOG intake before routing

The Controller MUST accept only a valid versioned AOG case and MUST identify missing or invalid required fields before specialist analysis.

#### Scenario: Valid case is routed
- **WHEN** the intake contains all required case fields and a supported schema version
- **THEN** the Controller records the case and proceeds with explicit specialist routing (ARD-CTL-001, ARD-CTL-004)

#### Scenario: Required case field is missing
- **WHEN** a required intake field is missing or invalid
- **THEN** the Controller returns field-specific findings, requests clarification, and does not produce a recovery recommendation (ARD-CTL-002, ARD-GOV-005)

### Requirement: Preserve specialist results and evidence state

The Controller MUST validate specialist results before aggregation and retain their evidence references, confidence, warnings, missing data, failures, and conflicts.

#### Scenario: Specialist result is incomplete or unavailable
- **WHEN** a specialist result is partial, malformed, or unavailable
- **THEN** the Controller identifies the affected analysis, marks the case incomplete, and does not invent a replacement finding (ARD-CTL-006, ARD-CTL-008, ARD-RES-003, ARD-RES-004, ARD-RES-006)

#### Scenario: Specialist evidence conflicts
- **WHEN** two specialist results materially disagree
- **THEN** the Controller preserves both claims and their sources, defers a preferred path, and marks the case for human adjudication (ARD-CTL-007, ARD-GOV-004)

### Requirement: Build and evaluate recovery candidates

The Controller MUST evaluate repair with the original part, repair with a preferred or alternate part, aircraft swap, and flight delay when supported by the case evidence.

#### Scenario: Candidates use specialist readiness and impact
- **WHEN** valid candidate inputs are available
- **THEN** each candidate uses its applicable sourcing method, Maintenance or Materials & Logistics readiness estimate, and Operations package-load plan before comparison (ARD-CTL-018)

### Requirement: Exclude noncompliant options before scoring

The Controller MUST exclude options without required airworthiness or engineering approval, or required part authorization and traceability, before calculating any score.

#### Scenario: Candidate fails a compliance check
- **WHEN** a candidate fails an applicable approval, authorization, or traceability check
- **THEN** it is listed with the reason and is not scored or ranked (ARD-CTL-017)

### Requirement: Rank eligible options deterministically

The Controller MUST score eligible options with the fixed 30/30/30/10 weights for speed, operational and package impact, risk, and total estimated cost.

#### Scenario: Identical evidence produces identical ranking
- **WHEN** the same validated evidence and scoring configuration are evaluated more than once
- **THEN** factor scores, weights, aggregate scores, and ranking are identical and traceable to their inputs (ARD-CTL-011, ARD-CTL-012, ARD-CTL-013)

#### Scenario: Top options are within two percentage points
- **WHEN** the top eligible options differ by no more than two percentage points
- **THEN** both options and their trade-offs are presented without asserting a unique preferred option, and human selection is required (ARD-CTL-014, ARD-CTL-015)

### Requirement: Produce an evidence-backed human decision brief

The Controller MUST return a sponsor-readable brief containing case status, findings, eligible ranked options, excluded options and reasons, trade-offs, risks, assumptions, warnings, confidence, and required human action.

#### Scenario: Complete high-confidence analysis
- **WHEN** required specialist results are complete, consistent, and confidence is at least 0.70
- **THEN** the Controller may identify a preferred path but labels it advisory and requires human approval (ARD-CTL-016, ARD-GOV-001, ARD-PRN-001, ARD-PRN-005)

#### Scenario: Provisional or low confidence
- **WHEN** confidence is from 0.50 through 0.69 or below 0.50
- **THEN** the Controller marks the result provisional or escalated respectively and identifies the human review or additional data needed (ARD-GOV-002, ARD-GOV-003)

### Requirement: Keep operational approval separate from agent output

The Controller MUST NOT treat chat text, a specialist result, a confidence score, or a test mode as human approval, and MUST NOT execute an operational action.

#### Scenario: User asks the Controller to execute or approve a plan
- **WHEN** a user asks the Controller to approve, book, reserve, transfer, purchase, ship, assign, delay, or reroute
- **THEN** the Controller explains that it can only provide advice, identifies the required human approvers, and performs no operational write (ARD-PRN-001, ARD-PRN-002, ARD-GOV-006, ARD-GOV-008, ARD-SEC-002)