# Spec Delta

## MODIFIED Requirements

### Requirement: Candidate options receive per-candidate specialist evaluation
The Controller MUST construct supported repair-original, repair-preferred/alternate, aircraft-swap, and delay candidates from validated evidence, with one candidate per sourcing path and candidate-specific package-load evidence. For repair, readiness MUST be the later of Maintenance readiness and selected sourcing ETA; the Controller MUST invoke Maintenance and Materials & Logistics concurrently per candidate, then Operations using that ETA. (ARD-CTL-018)

#### Scenario: Each sourcing path is evaluated as its own candidate
- **WHEN** validated evidence supports a repair candidate with multiple sourcing offers
- **THEN** the Controller creates a stable candidate for each offer, narrows its M&L request to that offer, retains its source and package evidence, and evaluates Operations using the later repair/source ETA with both evidence references (ARD-CTL-018, ARD-DAT-004..005)

#### Scenario: Each supported candidate is evaluated through all required domains
- **WHEN** validated case evidence supports multiple recovery candidates
- **THEN** each candidate has its own Maintenance and Materials & Logistics results and an Operations assessment tied to that candidate's readiness evidence and identifier (ARD-CTL-018, ARD-CTL-006)

#### Scenario: Required candidate evidence is missing
- **WHEN** a repair candidate lacks a required source ETA, readiness ETA, or package-load input
- **THEN** that candidate remains partial or unscored with the missing input named, no value is inferred from another candidate, and Operations does not receive a fabricated readiness ETA (ARD-CTL-008/018, ARD-GOV-005, ARD-RES-004)

#### Scenario: Per-candidate results remain unranked
- **WHEN** Operations returns assessments for the candidate set
- **THEN** the Controller preserves the assessments and their costs without assigning a weighted score, relative rank, or final recommendation at this orchestration stage (ARD-CTL-011..016, ARD-SYS-005)