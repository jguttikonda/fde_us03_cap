# Proposal

## Why

Verification of `orchestrate-aog-recovery-cases` confirmed that its component tests and unranked handoff work, but its specialist ports are not adapted to the existing Maintenance and Materials & Logistics input contracts, and Operations has no Controller-owned execution deadline. This focused follow-up binds those contracts end to end, keeps degraded outcomes visible, and verifies isolation and response boundaries before the orchestration is treated as operationally integrated. Routing and source-health enforcement are owned by `orchestrate-aog-recovery-cases` and are not in this change's scope.

## What Changes

- Add typed adapters from each candidate-scoped Controller request to the existing Maintenance and Materials & Logistics assessment input contracts. Preserve candidate identity, source evidence, readiness, sourcing and package-load inputs without changing specialist domain models or inferring values.
- Give the Operations boundary an explicit configurable deadline. A timeout must be candidate-local, produce a structured timeout/failure, name the missing analysis, lower confidence or escalate, and leave other candidates and cases unaffected.
- Constrain the ADK Controller entry point to the versioned deterministic workflow response contract. The model must not invent a fallback, rank candidates, or claim approval/action.
- Add concurrent two-case integration coverage, using fake specialist prompt runners and deterministic local Operations adapters, for adapter payload mapping, specialist and Operations failures, timeout cancellation/containment, H3/H4 append failure, and pending human approval.
- Repair Controller traceability documentation: consolidate the repeated aggregation row, place Controller mappings in the Controller evidence section, and distinguish the historical 74-test shared-foundation run from the current repository-wide result.

## Capabilities

### New Capabilities

- `controller-runtime-integration`: Translates candidate requests through existing typed agent contracts, bounds Operations execution, and preserves correlated case-isolated failure and response behavior.

### Modified Capabilities

None. The main spec inventory does not yet contain `recovery-orchestration`; its current delta is owned by the active/completed `orchestrate-aog-recovery-cases` change. This proposal adds a separate runtime-integration contract rather than claiming an existing main-spec path or changing specialist-domain requirements.

## Impact

- Affects `src/aog_recovery/controller/` workflow, orchestration, ADK boundary, and adapter modules; consumes existing `MaintenanceAssessmentInput`, `MaterialsLogisticsAssessmentInput`, `OperationsRequest`, settings, shared evidence, audit, and human-gate contracts.
- Adds deterministic adapter and concurrent workflow tests under `tests/` without live model, network, or airline calls.
- Updates `docs/shared-foundation-verification.md` and `docs/controller-orchestration-verification.md` so traceability and test evidence have one current, reviewable source.
- Adds no operational write capability, ranking/scoring/report generation, new provider, or live integration. Every handoff remains advisory and requires authorized human approval.

## ARD Traceability

### Addressed

- **ARD-CTL-006, ARD-CTL-008, ARD-CTL-018** — invoke existing typed specialist boundaries per candidate, preserve partial results, and retain the candidate evaluation sequence.
- **ARD-DAT-003..010/012** — preserve case/trace/correlation context, validate typed adapter inputs/results and evidence references, and reject malformed or unsupported data.
- **ARD-OPS-001..009** — consume the existing Operations contract without altering Operations domain logic; carry per-candidate readiness and outcome through a bounded Controller boundary.
- **ARD-GOV-002..005/008, ARD-RES-002..007** — make missing, stale, unavailable, timed-out, conflicting, or failed evidence visible; keep timeouts bounded; prevent degraded or high-confidence output from bypassing human approval; isolate case failures.
- **ARD-SEC-001..009, ARD-OBS-001..004, ARD-NFR-001..003/006** — preserve allowlisted read-only boundaries, validate untrusted data, emit correlated redacted events, and use explicit configured deadlines and deterministic tests.
- **ARD-TEC-002..005/007..009, ARD-TST-001..003/005/007..009, ARD-RUB-002..004** — retain the Google ADK boundary, Pydantic contracts, bounded asynchronous calls, pytest fakes, and reviewable verification/traceability evidence.

### Deferred

- **ARD-CTL-009/011..016/019, ARD-SYS-005, ARD-TST-004/006** — weighted scores, ranking, close-score behavior, final cost synthesis, final recommendation, decision brief, and ranked-recommendation scenarios remain in the separate `rank-aog-recovery-options` change.
- **ARD-GOV-006..007** — collecting human decisions and maintaining the final recommendation version remain separate; this change only preserves the pending human gate.
- **ARD-TEC-017..020, ARD-RUB-005..011, ARD-DEP-001 onward** — CI/security readiness, RAPID peer review, Go/No-Go, sponsor delivery/live Q&A, and deployment readiness remain human/project responsibilities.

### Out of Scope

- Any purchase, reservation, transfer, shipment, dispatch, aircraft assignment, flight delay, or other operational action (ARD-PRN-002, ARD-SEC-002..003).
- Changes to Maintenance, Materials & Logistics, or Operations domain behavior.
- Weighted ranking, final recommendation prose, decision-brief rendering, or automatic approval.

No ARD deviation is requested.

## Rubric and Capability Coverage

| Rubric checkbox / capability | Planned support | Retained evidence | Verification | Human responsibility |
|---|---|---|---|---|
| Phase 2: spec-driven design quality | Typed integration contracts and scoped runtime decisions | Proposal, design, specs, tasks, ARD mapping | Model-to-requirement-to-test consistency | Review boundary ownership and acceptance criteria |
| Phase 3: engineering quality | Real agent-input adapters, bounded Operations calls, correlated failure states | Source changes, deterministic tests, updated verification note | Full pytest, Ruff, format, and mypy gates | Peer review and accepted-risk disposition |
| Phase 4: degraded operation | Malformed payloads, timeouts, stale/conflicting evidence, and isolated case failures | Synthetic event trajectories and per-case handoffs | Concurrent two-case integration scenarios | Review degraded-mode and timeout policy |
| Human approval and safety | ADK response cannot replace deterministic output or human approval | Pending-gate assertions and no-action checks | High-confidence and degraded-mode non-bypass tests | Authorized Ops and Maintenance/airworthiness reviewers decide |
| AI-assisted practice and demonstration | Reproducible synthetic end-to-end scenario and traceability evidence | Updated implementation/evidence note | Scenario regression run | Team explains AI assistance, peer review, Go/No-Go, and sponsor demo |