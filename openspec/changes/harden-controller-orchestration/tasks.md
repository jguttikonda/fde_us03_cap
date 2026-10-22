# Tasks

## 1. Specialist Boundary Adapters

- [ ] 1.1 Add typed candidate-to-Maintenance and candidate-to-Materials & Logistics adapters using the existing assessment input models; verify inputs preserve candidate/case identity, source evidence, readiness, and sourcing without inferred values using fake prompt runners (ARD-CTL-006/018, ARD-DAT-003..006/009..010, ARD-TEC-003/005).
- [ ] 1.2 Verify malformed or unresolved specialist input becomes a candidate-local structured failure and does not call the affected specialist; preserve supported results for other candidates and update the adapter traceability row (ARD-CTL-006/008, ARD-DAT-008..010, ARD-RES-003..004, ARD-GOV-005).

## 2. Bounded Operations Invocation

- [ ] 2.1 Implement a typed asynchronous Operations adapter with a configured deadline and bounded cancellation/worker behavior; verify the current deterministic Operations implementation remains unchanged and all calls have finite execution bounds (ARD-RES-002/005, ARD-NFR-001..002, ARD-TEC-007).
- [ ] 2.2 Test a real waiting fake that exceeds the configured deadline; verify structured timeout metadata, missing Operations analysis, confidence reduction/escalation, candidate isolation, and a correlated timeout event (ARD-RES-002..004/007, ARD-CTL-008/018, ARD-OBS-001..003).

## 3. ADK Response Contract

- [ ] 3.1 Add a versioned Pydantic Controller ADK response model and bind it to the ADK entry point; verify the deterministic handoff schema and agent configuration without invoking a model or network (ARD-TEC-002..005, ARD-DAT-001/006/010, ARD-TST-009).
- [ ] 3.2 Test invalid workflow output and untrusted input handling at the ADK boundary; verify failures remain explicit, no model-generated success fallback appears, and no score/rank/approval/action field is exposed (ARD-SEC-003..005/008, ARD-GOV-008, ARD-PRN-001..006).

## 4. Concurrent Case Integration

- [ ] 4.1 Add a deterministic two-case concurrent end-to-end test with distinct trace contexts and a failure in only one case; verify each handoff, source result, context event, and status remains case-isolated (ARD-RES-007, ARD-OBS-001..004, ARD-SEC-007/009, ARD-NFR-002).
- [ ] 4.2 Extend the end-to-end scenario matrix for specialist adapter mapping, Operations timeout/cancellation, H3/H4 recording failure, compliance exclusion, conflicts, and pending human approval; verify every case has a requirement-to-test trace entry (ARD-TST-001..003/005/007..009, ARD-CTL-006..008/017..018, ARD-GOV-004..008).

## 5. Evidence and Traceability

- [ ] 5.1 Consolidate Controller requirement/event mappings into one current evidence section, remove duplicate rows, and label the shared-foundation 74-test result as historical; verify the Controller evidence note reports the latest test total and modified-file inventory (ARD-OBS-001..004, ARD-TST-001/008, ARD-RUB-002..004).
- [ ] 5.2 Run and retain `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy src`; record actual output, warnings, and modified-file/test inventory in the reviewable verification note (ARD-TST-001/008, ARD-TEC-009, ARD-RUB-002..004).
- [ ] 5.3 Retain a synthetic integrated demonstration and AI-assisted iteration/traceability evidence; document that ranking/reporting remains in `rank-aog-recovery-options` and that RAPID review, Go/No-Go, sponsor delivery/live Q&A, and operational/airworthiness approvals remain human responsibilities (ARD-TST-001/006, ARD-TEC-019..020, ARD-RUB-005..011).

## Workflow follow-up

- Archive this change only after implementation, verification, and required human review are complete.