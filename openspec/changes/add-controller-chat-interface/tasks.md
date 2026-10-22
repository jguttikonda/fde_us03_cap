# Tasks

## 1. Controller Contracts and Intake

- [x] 1.1 Define versioned Pydantic contracts for Controller intake, workflow status, candidate state, exclusions, score factors, and decision brief; add valid/invalid contract tests and verify with `uv run pytest tests/controller/test_contracts.py` (ARD-TEC-003, ARD-CTL-001..002, ARD-DAT-009..010, ARD-TST-002).
- [x] 1.2 Implement case-scoped intake validation, clarification findings, explicit routing records, and correlated audit events; test complete and incomplete cases plus isolated case IDs with `uv run pytest tests/controller/test_intake.py tests/controller/test_context.py` (ARD-CTL-001..005, ARD-PRN-008, ARD-OBS-001..004, ARD-RES-007).

## 2. Specialist Orchestration

- [x] 2.1 Coordinate Maintenance and Materials & Logistics per repair candidate and Operations with the resulting readiness estimate; validate every specialist result and record the Materials/Maintenance peer exchange; verify normal orchestration and evidence references with focused integration tests (ARD-CTL-006, ARD-CTL-008..009, ARD-CTL-018, ARD-PRN-007..008).
- [x] 2.2 Build repair, swap, and delay candidates from supported case evidence; add scenarios for local stock, remote stock, unavailable stock, missing inputs, specialist failure, stale evidence, and conflicting estimates; verify each degraded case remains visible and is not success-shaped (ARD-CTL-007..008, ARD-RES-002..007, ARD-GOV-004..005, ARD-TST-003, ARD-TST-006, ARD-TST-009).

## 3. Compliance, Scoring, and Brief

- [x] 3.1 Implement the deterministic compliance gate before ranking and retain each excluded option with its reason; test missing approval and unauthorized/untraceable part scenarios and verify excluded options never receive scores (ARD-CTL-017, ARD-PRN-003, ARD-TST-004).
- [x] 3.2 Implement deterministic 30/30/30/10 scoring, total mock cost aggregation, factor-level explanations, stable ranking, and the two-percentage-point close-score rule; verify boundaries and repeatability with focused scoring tests (ARD-CTL-011..015, ARD-CTL-019, ARD-PRN-003, ARD-TST-004, ARD-TST-009).
- [x] 3.3 Assemble the typed decision brief with confidence thresholds, missing-data and conflict state, recommendation narrative, required human action, and terminal workflow status; test preferred, provisional, escalated, and close-score briefs (ARD-CTL-009..010, ARD-CTL-016, ARD-GOV-001..005, ARD-RES-004, ARD-TST-001).

## 4. ADK Web Chat

- [x] 4.1 Add a Controller ADK Web root agent with a narrow typed workflow tool; test agent construction, tool allowlist, prompt boundary, and that tests make no model or network call (ARD-TEC-002, ARD-TEC-005, ARD-SEC-001..005, ARD-TST-007, ARD-TST-009).
- [x] 4.2 Implement conversational intake clarification and a plain-language rendering of the validated brief that preserves scores, exclusions, confidence, evidence, and approval caveats; test missing fields, prompt-injection attempts, execution requests, and partial/failure responses (ARD-PRN-004..006, ARD-SEC-004..008, ARD-GOV-008, ARD-TST-005, ARD-TST-007).
- [x] 4.3 Document local ADK Web startup, environment/key setup, synthetic scenario prompts, expected response behavior, and prototype limitations; verify each documented command and retain a repeatable demonstration checklist (ARD-TEC-014, ARD-TEC-019, ARD-DEP-001..002, Rubric Category 6).

## 5. Integration Verification and Evidence

- [x] 5.1 Run end-to-end synthetic chat scenarios for successful repair, remote-part transfer, unavailable part with swap alternative, source failure, conflicting ETA, low confidence, and close scores; verify the final response matches the typed brief and always requires human approval (ARD-TST-003..006, ARD-TST-008..009, ARD-GOV-008).
- [x] 5.2 Run Ruff, mypy, and the focused/full pytest suites; summarize outcomes, limitations, unresolved issues, and retained RAPID/AI-assistance/demo evidence in the project evidence artifacts (ARD-TEC-009, ARD-TEC-017, ARD-TEC-019, ARD-TST-001, ARD-TST-008, Rubric Categories 2..6).