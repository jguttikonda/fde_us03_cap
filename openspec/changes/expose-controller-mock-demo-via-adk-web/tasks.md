# Tasks

## 1. Deterministic Controller Demo Workflow

- [x] 1.1 Add a fixed scenario registry and typed synthetic AOG intake/evidence for `happy_path`, `cache_degraded`, `time_conflict`, and `close_score_choice`; use no live model or enterprise input and preserve source IDs, timestamps, and degradation state. Verify each scenario input against `ControllerIntake` and assert repeatable values (ARD-DAT-001..006, ARD-RES-001/006, ARD-TST-002/009).
- [x] 1.2 Add deterministic Maintenance and Materials & Logistics specialist ports plus local Operations adapters, then compose the real `ControllerWorkflow` with a fixed clock and case-scoped in-memory recorder. Verify each scenario reaches its expected Controller report, H3/H4/audit evidence where applicable, conflict/escalation or close-score selection, and pending human gate (ARD-CTL-005..008/017..019, ARD-SYS-004..005, ARD-OBS-001..004, ARD-GOV-004..008, ARD-TST-001/003..006/009).

## 2. Controller ADK Web Entry Point

- [x] 2.1 Add an ADK Web Controller root using the existing typed Controller response boundary and a scenario-name dispatcher that delegates only to the deterministic workflow. Require the configured non-placeholder model credential for web startup; do not expose arbitrary case-data or operational-action tools. Verify root construction, typed response schema, startup rejection for missing/placeholder credentials, and secret redaction (ARD-TEC-002/005, ARD-DEP-001..002, ARD-SEC-001..003/006, ARD-GOV-008).
- [x] 2.2 Add ADK tool-boundary integration tests that invoke all four scenario names without a model/network call. Assert repeatable report output, visible evidence and failures, close-score group, structured unknown-scenario response, pending approval, and no operational actions; verify network access is blocked during tests (capstone-demonstration: Controller ADK Web runs complete synthetic recovery scenarios; ARD-TST-001/006/009, ARD-RES-001/006, ARD-GOV-004..008, ARD-SEC-008).

## 3. User Guidance and Readiness Evidence

- [x] 3.1 Update README and `docs/capstone-demo-runbook.md` with the ADK Web launch command, local setup and model credential requirements, supported scenario prompts and expected reports, and the boundary between synthetic enterprise data and model-provider traffic. Clarify failure/credential behavior and that no live systems or operational writes are used. Verify documented commands and demo outputs (ARD-DEP-001..003/006, ARD-SEC-006, ARD-RUB-010..011, ARD-TEC-019..020).
- [x] 3.2 Update Controller scenario-to-test and readiness evidence maps with the Web entry point, named scenarios, credential checks, tests, limitations, and pending human review; run focused and full pytest with coverage, Ruff check/format, mypy, strict OpenSpec validation, and selected Bandit, pip-audit, and Gitleaks scans. Record exact results and remaining findings without weakening contracts (ARD-TST-001..009, ARD-CAP-001..003, ARD-TEC-008/017..020, ARD-DEP-005, ARD-RUB-002..009).
