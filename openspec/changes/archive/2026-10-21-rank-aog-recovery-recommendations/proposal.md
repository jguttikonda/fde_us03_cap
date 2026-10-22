# Proposal

## Why

The Controller currently stops after per-candidate specialist evaluation and compliance screening, returning an unranked handoff. Operators therefore do not yet receive the deterministic, evidence-backed comparison and decision-ready approval record required to choose among compliant AOG recovery paths. Completing that Controller-owned stage now closes the workflow without introducing another agent or allowing automated operational action.

## What Changes

- Extend the Controller workflow from the existing unranked handoff to a complete decision brief, retaining candidate-specific findings from Maintenance, Materials & Logistics, and Operations.
- Compare repair with the original part, repair with a preferred or alternate part, aircraft swap, and flight delay. Preserve concurrent Maintenance and Materials & Logistics evaluation per candidate, followed by Operations evaluation using the resulting readiness ETA.
- Expand each repair sourcing offer into its own candidate, narrow its M&L request to that offer, and use the later of repair readiness and selected source ETA for Operations; missing source ETA remains visible and unscored.
- Run the compliance gate before scoring. Exclude failed or unverified engineering approval, part authorization, and traceability with explicit reasons; excluded candidates never receive scores or ranks.
- Deterministically score eligible options using the ARD baseline weights: speed 30%, operational and package impact 30%, risk 30%, and total estimated cost 10%. Keep estimated cost in USD and show factor scores, weights, aggregate score, evidence references, trade-offs, assumptions, risks, warnings, and uncertainty.
- Present top options within 2 percentage points together for human selection. Preserve provisional status for confidence from 0.50 through 0.69, escalate below 0.50 or on material evidence conflict, and never imply that a score or confidence value approves a choice.
- Produce a structured decision-ready report and append-only human decision records for approve, reject, escalate, or request-more-information actions. Approval requires both the Ops lead and Maintenance/airworthiness authority, records the recommendation version reviewed, and remains separate from recommendation generation.
- Add focused unit, contract, and workflow tests for score determinism and boundaries, compliance exclusions, incomplete or conflicting evidence, close scores, report contents, approval actions, dual approval, audit linkage, and the no-execution boundary.

## Capabilities

### New Capabilities

- `recovery-recommendations`: deterministic compliance-first ranking, decision-brief generation, and auditable human decision handling owned by the Controller (not a separate agent).

### Modified Capabilities

- `recovery-orchestration`: make candidate construction and specialist evaluation source-specific, combine repair and selected sourcing ETAs conservatively, and retain both evidence trails.
- `controller-runtime-integration`: expose the completed ranked decision brief and human-gate state at the Controller runtime boundary while preserving advisory-only behavior and existing typed failures.

## Impact

- Controller models, scoring/report assembly, workflow composition, compliance handoff, human-gate integration, and audit recording under `src/aog_recovery/controller/`, `src/aog_recovery/contracts/`, and `src/aog_recovery/validation/`.
- Existing Controller contract and integration tests, with new focused tests in the established `tests/contracts/` and `tests/integration/` suites.
- No new agent, operational write adapter, live external system, or dependency is required. Specialist contracts and local/mock adapters remain the evidence boundary. Existing outputs and decision records are extended or composed without allowing any agent to execute recovery actions.

## ARD Traceability

### Addressed

- `ARD-SYS-002`, `ARD-SYS-005..006`: Controller owns comparison, deterministic scoring, ranking, explanation, decision brief, and workflow; only the human boundary may decide.
- `ARD-DAT-004..006`, `ARD-DAT-011..012`: reports preserve evidence provenance, fact/assumption separation, normalized confidence, decision status, and supported recovery-option types.
- `ARD-CTL-009..019`: recommendation generation, terminal status, weighted score, deterministic calculation, factor transparency, ranked alternatives, close-score handling, decision brief, compliance-first eligibility, candidate evaluation, and USD cost model.
- `ARD-GOV-001..008`, `ARD-PRN-001..003/005..008`: confidence thresholds, conflict and missing-input handling, required human actions and records, mandatory approval, deterministic controls, evidence grounding, visible degradation, typed boundaries, and case-level traceability.
- `ARD-OPS-009`: package redistribution and unprotected packages remain ranking inputs and visible report evidence.
- `ARD-RES-001..007`, `ARD-SEC-002..003/007..009`, `ARD-OBS-001..004`: preserve degraded results, case isolation, read-only/allowlisted access, non-sensitive audit events, and reconstructable recommendation and decision history.
- `ARD-TST-001..009`, `ARD-TEC-002/005/008/017/019`, `ARD-NFR-001..002`: requirement-linked contract, deterministic scoring, workflow, human-gate, failure, security-boundary, regression, AI-assistance evidence, and bounded-execution verification.

### Deferred

- Sponsor demonstration and RAPID Go/No-Go sign-off remain delivery-stage evidence; this change will retain review inputs but will not claim those human activities are complete (`ARD-TEC-020`).

### Out of Scope

- Live enterprise-system integration, deployment/readiness changes, and any operational write or execution capability (`ARD-SYS-007..009`, `ARD-SEC-001..006`, `ARD-DEP-001..003`). Existing typed local/mock and read-only boundaries remain in force.
- Changes to bounded LLM prompt structure or specialist reasoning are out of scope; the Controller report uses deterministic fields and templates (`ARD-PRN-004`).
- Changes to specialist domain reasoning, Maintenance/M&L A2A payloads, or Operations package-allocation policy beyond consuming their validated findings.

No ARD requirement is weakened or waived. Requiring both approver roles for a recommendation follows the requested stricter dual-approval policy; no approval, confidence level, or test mode can bypass the human boundary.

## Rubric and Capability Coverage

| Rubric / capability | Frameworks and retained evidence | Verification | Human responsibility |
|---|---|---|---|
| Phase 2: spec-driven design, explicit requirements and scenarios | OpenSpec `recovery-recommendations` capability and `recovery-orchestration` / `controller-runtime-integration` deltas; ARD traceability in proposal, design, spec, and tasks | Validate OpenSpec artifacts and trace each requirement to scenarios and tasks | Review and accept scope and assumptions |
| Phase 3: explainable, structured recommendation | Pydantic decision/report contracts; deterministic Controller score and report; evidence references and score factors | Contract tests and unit tests for normalization, weights, ranking, cost, exclusions, close scores, and reproducibility | Inspect evidence, assumptions, trade-offs, and warnings |
| Phase 4: normal, edge, degraded, and regression behavior | Fixed mock fixtures; retained pytest output and regression scenarios | Workflow tests for missing/stale/conflicting data, failures, confidence thresholds, zero viable candidates, and escalation | Resolve conflicts or provide missing information |
| Phase 5: RAPID and approval readiness | Human decision records, recommendation version, audit trajectory; RAPID review evidence remains a delivery artifact | Verify case/version linkage, reviewer identity, timestamps, rationale, and both approval roles | Ops lead and Maintenance/airworthiness authority make and record the final decision |
| Phase 6: sponsor communication | Decision brief with concise recommendation narrative and technical evidence | Review report readability and sponsor demonstration evidence when scheduled | Sponsor/team explains limits, risks, and the approval boundary |
