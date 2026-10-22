# Tasks

## 1. Controller Contracts and Case Context

- [x] 1.1 Add versioned Pydantic Controller intake, routing decision, per-candidate result, workflow status, and unranked handoff contracts that reuse shared `AogCase`, `AgentResult`, `StructuredError`, evidence, confidence, and human-decision types; test valid, invalid, unsupported-version, and unknown-field payloads and map each contract to its ARD (ARD-DAT-001..011, ARD-CTL-001/006/010).
- [x] 1.2 Add an append-only, case-isolated Controller context store and H3/H4 recorder adapter carrying case/trace/correlation IDs, timestamps, direction, status, and evidence references; test ordering, idempotency, append failure, and cross-case isolation; document the persistence seam and event schema (ARD-CTL-005, ARD-SYS-002/004, ARD-OBS-001..004, ARD-SEC-009, ARD-RES-007).

## 2. Intake and Routing

- [x] 2.1 Implement deterministic AOG intake validation and explicit source-health/routing records for selected and omitted specialists; test missing/invalid input causes no invocation, normal routing, source-unavailable visibility, and rejection of untrusted extra fields; update requirement-to-model-to-test traceability (ARD-CTL-001..004, ARD-DAT-009..010, ARD-SEC-003..005, ARD-TST-002/007).
- [x] 2.2 Enforce the validated routing decision at runtime: never invoke omitted roles, skip explicitly unavailable selected roles, preserve route/source-health records in the handoff, and keep affected analysis partial or escalated; verify omitted/unavailable fake ports receive zero calls and update routing traceability (ARD-CTL-003..006/008, ARD-GOV-005, ARD-RES-003..004, ARD-TST-002/007).

## 3. Candidate Construction and Specialist Invocation

- [x] 3.1 Build stable unranked repair-original, repair-preferred/alternate, swap, and delay candidates from validated case evidence, including candidate-specific sourcing and package-load inputs; leave unsupported values missing instead of inventing them; test deterministic IDs, missing evidence, and no score/rank fields (ARD-CTL-018, ARD-DAT-012, ARD-GOV-005, ARD-PRN-003).
- [x] 3.2 Invoke Maintenance and Materials & Logistics concurrently for each candidate through typed fakeable boundaries with bounded timeouts, then persist their existing H3/H4 exchange through Controller context; test per-candidate correlation, timeout/failure isolation, H3/H4 ordering, and visible partial status; update traceability (ARD-CTL-006/008/018, ARD-SYS-004, ARD-RES-003..005/007, ARD-NFR-001..002).
- [x] 3.3 Invoke Operations once per candidate after readiness evidence is available, using its versioned request and preserving its per-candidate outcome without changing Operations domain logic; test readiness provenance, missing ETA handling, package/cost result retention, and no candidate ranking (ARD-CTL-006/018, ARD-OPS-001..009, ARD-DAT-003..006, ARD-TST-003/009).

## 4. Aggregation, Compliance, and Approval Boundary

- [x] 4.1 Validate shared and role-specific specialist results and evidence references, aggregate supported findings, and preserve missing data, warnings, unknowns, and contradictory values; test malformed references, source failure, conflicts, and deterministic confidence caps/escalation; update traceability (ARD-CTL-006..008, ARD-DAT-004..010, ARD-GOV-002..005, ARD-RES-003..006).
- [x] 4.2 Apply the compliance gate to candidate eligibility and produce an unranked handoff with explicit exclusions and pending human-gate state; test unknown/failed part authorization, missing repair approval, high-confidence non-bypass, no score/rank/recommended-winner fields, and absence of operational action methods (ARD-CTL-017, ARD-SYS-005..006, ARD-GOV-001..008, ARD-SEC-001..003/008, ARD-TST-005).
- [x] 4.3 Emit correlated audit events for intake, routing, invocation, timeout/failure, conflict, aggregation, and handoff; test event metadata, redaction boundaries, bounded execution, and case isolation; retain the event-to-requirement map (ARD-PRN-008, ARD-OBS-001..004, ARD-RES-005/007, ARD-SEC-006..009, ARD-NFR-001..003).

## 5. Integrated Verification and Evidence

- [x] 5.1 Add deterministic end-to-end scenarios using fake specialist boundaries and mock adapters for normal multi-candidate orchestration, Operations timeout, missing/stale/conflicting evidence, failed candidate isolation, H3/H4 recording failure, compliance exclusion, and pending human approval; verify an unranked handoff and update model-to-test traceability (ARD-TST-001..003/005/007..009, ARD-PRN-001..008, ARD-CTL-006..008/017..018, ARD-OBS-001..004).
- [x] 5.2 Run and retain `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src`; record actual outputs, residual warnings, and the modified-file/test inventory in a reviewable evidence note (ARD-TST-001/008, ARD-TEC-009, ARD-RUB-002..004).
- [x] 5.3 Retain a synthetic orchestration demonstration and inspectable AI-assisted iteration/traceability evidence; document that final ranking, decision brief, RAPID sign-off, Go/No-Go, sponsor delivery/live Q&A, and all operational/airworthiness approval remain deferred to the named later change and authorized people (ARD-TST-001/006, ARD-TEC-019..020, ARD-RUB-005..011).
