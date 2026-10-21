# Tasks

## 1. Python and ADK Foundation

- [ ] 1.1 Verify currently supported Python, Google ADK, Pydantic, `pydantic-settings`, pytest, and Ruff versions; declare compatible runtime and development dependency groups and the supported Python range in `pyproject.toml`, then verify the documented clean-environment install command succeeds (ARD-TEC-001..004, ARD-TEC-008..014, ARD-NFR-007).
- [ ] 1.2 Create the documented `src/aog_recovery/` package boundaries for contracts, validation, adapters, settings, observability, and ADK integration without implementing any specialist agent reasoning; verify imports and package discovery using the configured lint/type/test commands (ARD-TEC-002, ARD-NFR-004..005, Spec: Versioned AOG case contract).

## 2. Shared Contracts

- [ ] 2.1 Implement strict, versioned Pydantic models for AOG case intake, schema version, event timestamps, and trace context; add valid/invalid field tests and concise contract documentation confirming invalid intake is not defaulted (ARD-DAT-001..003, ARD-DAT-009..010, ARD-CTL-001..002, Spec: Versioned AOG case contract).
- [ ] 2.2 Implement evidence, assumption, unknown, warning, and conflict contracts with source, retrieval time, validity state, and claim reference; test provenance retention and partial/stale/conflicting evidence representation (ARD-DAT-004..005, ARD-GOV-004..005, ARD-RES-006, Spec: Provenance-aware evidence contract).
- [ ] 2.3 Implement the common versioned agent-result envelope, normalized confidence constraints, role-specific payload boundary, structured errors, and recovery-option type; test schema rejection, output shape, and confidence range without adding agent reasoning (ARD-DAT-006, ARD-DAT-008, ARD-DAT-010..012, ARD-CTL-006, ARD-RUB-004, Spec: Typed agent result and confidence contract).
- [ ] 2.4 Implement versioned typed tool request/result, human decision, and audit event models; test required correlation/source/status fields, explicit error shape, recommendation-version binding, and role-attributed approval records (ARD-DAT-003, ARD-DAT-007..010, ARD-GOV-006..007, ARD-OBS-002, Spec: Explicit tool result contract; Spec: Human approval is a separate decision).

## 3. Deterministic Validation and Governance

- [ ] 3.1 Implement deterministic intake, schema, cross-field, evidence-reference, and result validators that return explicit field-level findings; test reproducibility for identical inputs and rejection of malformed or unsupported-version inputs (ARD-DAT-009..010, ARD-CTL-001..002, ARD-TST-002, ARD-NFR-003, Spec: Deterministic boundary validation).
- [ ] 3.2 Implement confidence classification for `>= 0.70`, `0.50–<0.70`, and `<0.50`, plus conflict-driven escalation independent of score; test exact boundary values and ensure missing evidence is not inferred (ARD-GOV-001..005, ARD-DAT-005..006, Spec: Typed agent result and confidence contract).
- [ ] 3.3 Implement human-decision validation requiring both Ops lead and Maintenance/airworthiness authority for repair or part decisions; test approval, rejection, escalation, request-for-information, missing-role, stale-recommendation-version, and no-agent-bypass cases (ARD-GOV-006..008, ARD-TST-005, Spec: Human approval is a separate decision).

## 4. Read-Only Adapter Contracts

- [ ] 4.1 Define typed, allowlisted, read-only adapter protocols and deterministic local/mock implementations using explicit fixture inputs; test repeatable outputs, access restrictions, and absence of operational write methods (ARD-SYS-007..009, ARD-SEC-001..003, ARD-NFR-003, Spec: Read-only adapter boundary).
- [ ] 4.2 Add mock modes for unavailable, timeout, stale, malformed, partial, and conflicting responses; test structured errors, warning visibility, retry bounds/idempotency where retries are used, and absence of success-shaped fallback (ARD-RES-001..007, ARD-SEC-004, ARD-TST-002, Spec: Explicit tool result contract; Spec: Read-only adapter boundary).
- [ ] 4.3 Document the future live-adapter extension seam and its required separate approval for credentials, permissions, transport, and security verification; verify the foundation remains runnable without enterprise connectivity (ARD-SYS-008..009, ARD-SEC-001..006, ARD-NFR-005).

## 5. Settings, Correlation, and Audit Logging

- [ ] 5.1 Implement typed environment-based settings for adapter selection, configured timeout bounds, and non-secret policy values; test valid settings, invalid-setting errors, and secret exclusion from serialization/logs (ARD-TEC-004, ARD-SEC-006..007, ARD-NFR-001/006, Spec: Validated externalized configuration).
- [ ] 5.2 Implement structured JSON logging and correlation propagation for case, trace, and request identifiers across ADK-facing boundaries, tools, adapters, and audit events; test required event fields and correlation continuity (ARD-DAT-003, ARD-OBS-001..003, Spec: Correlated structured audit events).
- [ ] 5.3 Implement redaction and append-oriented audit serialization for failures, conflicts, escalations, and human decisions; test sensitive-value redaction and verify event details use concise rationale and evidence references rather than private chain-of-thought (ARD-SEC-006..009, ARD-OBS-003..004, Spec: Correlated structured audit events).

## 6. Reusable Tests and Traceability

- [ ] 6.1 Add reusable synthetic pytest fixtures for valid and invalid cases, evidence states, result envelopes, tool success/failure, human decisions, trace context, and local adapters; verify fixtures are deterministic and contain no real operational or secret data (ARD-TEC-008, ARD-TST-002..003, ARD-NFR-003, ARD-RUB-001).
- [ ] 6.2 Add focused contract and integration tests covering normal input, partial/stale/conflicting evidence, unavailable/malformed adapters, low-confidence escalation, trace propagation, redaction, and human approval; run pytest, Ruff, and configured type checks and retain a concise results summary (ARD-TST-001..003/005, ARD-RES-001..007, ARD-OBS-001..004, ARD-SEC-001..009, ARD-RUB-002..004).
- [ ] 6.3 Update requirement-to-model-to-test traceability and retain the change's inspectable AI-assisted design/iteration evidence, a focused modified-file/test inventory suitable for RAPID peer review, and a deterministic synthetic fixture scenario suitable for sponsor demonstration; verify evidence points to actual test outputs and clearly leaves human review, Go/No-Go, and live sponsor communication to people (ARD-TST-001, ARD-RUB-005..011, ARD-TEC-019..020).
