# Shared Foundation Verification

## Environment

- Python 3.14.7
- Google ADK 2.12.0
- Pydantic 2.14.1
- pydantic-settings 2.16.1
- pytest 9.1.1
- Ruff 0.17.1
- mypy 1.20.2
- `uv sync --all-groups --locked`: passed

## Results

| Check | Command | Result |
|---|---|---|
| Contract, validation, adapter, settings, audit, fixture, and integration tests | `uv run pytest` | 74 passed |
| Lint | `uv run ruff check .` | All checks passed |
| Formatting | `uv run ruff format --check .` | 89 files already formatted |
| Type checking | `uv run mypy src` | Success, no issues in 23 source files |

The test data is synthetic and deterministic. These results validate local
contracts and mocks only; they do not represent live enterprise connectivity,
airworthiness approval, operational execution, sponsor approval, or Go/No-Go.

## Requirement-to-Model-to-Test Traceability

| Requirements | Models and deterministic controls | Verification evidence |
|---|---|---|
| ARD-DAT-001..003, ARD-DAT-009..010, ARD-CTL-001..002 | `contracts/case.py`: strict versioned `AogCase` and `TraceContext`; `validation/boundaries.py`: deterministic field findings | `tests/contracts/test_case_contract.py`; `tests/validation/test_boundary_validation.py` |
| ARD-DAT-004..005, ARD-GOV-004..005, ARD-RES-006 | `contracts/evidence.py`: source, retrieval time, validity, claim, unknown and conflict records; `validation/confidence.py`: conflict override | `tests/contracts/test_evidence_contract.py`; `tests/validation/test_confidence_assessment.py`; adapter degraded-mode tests |
| ARD-DAT-006, ARD-DAT-008, ARD-DAT-010..012, ARD-CTL-006, ARD-RUB-004 | `contracts/agent.py`: versioned result, bounded confidence, structured error, recovery option | `tests/contracts/test_agent_contract.py`; `tests/validation/test_boundary_validation.py` |
| ARD-DAT-003, ARD-DAT-007..010, ARD-GOV-006..008, ARD-OBS-001..004, ARD-TST-005 | `contracts/tool.py`, `contracts/governance.py`, `contracts/audit.py`; `validation/human_gate.py`; correlated JSON audit boundary | `tests/contracts/test_tool_decision_audit_contract.py`; `tests/validation/test_human_gate.py`; `tests/observability/test_structured_audit.py` |
| ARD-SYS-007..009, ARD-SEC-001..004, ARD-RES-001..007, ARD-NFR-003/005 | `adapters/protocols.py`, `adapters/local.py`: role allowlist, read-only interface, deterministic degraded modes | `tests/adapters/test_local_adapter.py`; `tests/integration/test_shared_foundation_scenarios.py` |
| ARD-TEC-004, ARD-SEC-006..007, ARD-NFR-001/006 | `config.py`: typed local adapter mode, bounded timeouts, ordered thresholds, secret exclusion | `tests/settings/test_settings.py` |
| ARD-DAT-003, ARD-OBS-001..003 | `observability/context.py`, `observability/structured.py`, `adk/context.py`: case/trace/request propagation and structured events | Adapter correlation assertions in `tests/adapters/test_local_adapter.py`; event shape in `tests/contracts/test_tool_decision_audit_contract.py` |
| ARD-CTL-001..006/008, ARD-DAT-009..010, ARD-SEC-003..005, ARD-TST-002/007 | `controller/models.py`, `controller/intake.py`, `controller/workflow.py`, `controller/orchestration.py`: strict intake, field-level findings, explicit routing/source health enforced as the specialist invocation allowlist, and route state preserved in handoff | `tests/contracts/test_controller_contracts.py`, `tests/integration/test_controller_workflow.py`: invalid input without invocation, omitted-role suppression, unavailable-source suppression, and visible route/source status |
| ARD-CTL-018, ARD-DAT-012, ARD-GOV-005, ARD-PRN-003 | `controller/models.py`, `controller/candidates.py`: stable candidate IDs from evidence references; optional readiness, sourcing, and package-load inputs remain missing when unsupported | `tests/contracts/test_controller_contracts.py`: four candidate kinds, repeatable IDs, missing-input preservation, and absence of score/rank fields |
| ARD-CTL-006/008/018, ARD-SYS-004, ARD-RES-003..005/007, ARD-NFR-001..002 | `controller/orchestration.py`: typed concurrent Maintenance/M&L ports, bounded calls, structured failures, per-candidate results, and H3/H4 context recording | `tests/integration/test_controller_specialist_fanout.py`: concurrent calls, ordered H3/H4 records, timeout isolation, and visible partial status |
| ARD-CTL-006/018, ARD-OPS-001..009, ARD-DAT-003..006, ARD-TST-003/009 | `controller/orchestration.py`: one versioned Operations request per candidate, source-backed readiness, and full outcome retention without Controller ranking | `tests/integration/test_controller_specialist_fanout.py`: missing ETA remains absent; package and cost outcome fields are retained |
| ARD-CTL-006..008, ARD-DAT-004..010, ARD-GOV-002..005, ARD-RES-003..006 | `controller/aggregation.py`: validates shared/role-specific results and evidence references, preserves degraded data and conflicts, and applies deterministic confidence caps | `tests/integration/test_controller_specialist_fanout.py`: malformed reference, failed source, conflicting sources, deterministic escalation, and missing-result cases |
| ARD-CTL-017, ARD-SYS-005..006, ARD-GOV-001..008, ARD-SEC-001..003/008, ARD-TST-005 | `controller/compliance.py`: excludes repair candidates with unknown/failed approval, authorization, traceability, stale provenance, or incompatibility; hands off unranked candidates with a pending shared human gate | `tests/integration/test_controller_compliance.py`: authorized eligible path, unknown/unauthorized/not-traceable parts, missing engineering approval, failed Materials source, high-confidence non-bypass, no execution methods |
| ARD-PRN-008, ARD-OBS-001..004, ARD-RES-005/007, ARD-SEC-006..009, ARD-NFR-001..003 | `controller/context.py`, `controller/intake.py`, `controller/orchestration.py`, `controller/compliance.py`: correlated, append-only, redacted lifecycle events; append failures remain structured and visible | `tests/contracts/test_controller_contracts.py`, `tests/integration/test_controller_specialist_fanout.py`, `tests/integration/test_controller_compliance.py`, `tests/integration/test_h3_h4_recorder.py` |
| ARD-TST-001..003/005/007..009, ARD-PRN-001..008, ARD-CTL-006..008/017..018, ARD-OBS-001..004 | `controller/workflow.py`: deterministic intake-to-unranked-handoff composition over fakeable specialists and mock-backed Operations | `tests/integration/test_controller_workflow.py`: multi-candidate handoff, missing/stale/conflicting evidence, failed candidate isolation, Operations timeout, H3/H4 recording failure, compliance exclusion, invalid intake, and pending human approval |

### Controller Audit Event Map

| Event type | Requirements | Emission point |
|---|---|---|
| `controller_intake_validation`, `controller_routing` | ARD-CTL-001..004, ARD-DAT-001..003/009..010, ARD-SEC-003..005 | `controller/intake.py` after validation and deterministic routing; rejected input is recorded only when valid case/trace identity is present |
| `specialist_invocation`, `specialist_result`, `specialist_timeout`, `specialist_failure` | ARD-CTL-006/008/018, ARD-RES-002..005/007, ARD-NFR-001..002 | `controller/orchestration.py` around bounded Maintenance and Materials & Logistics calls |
| `operations_invocation`, `operations_result`, `operations_failure` | ARD-CTL-006/018, ARD-OPS-001..009, ARD-RES-003..005 | `controller/orchestration.py` around one Operations request per candidate |
| `peer_exchange` | ARD-SYS-004, ARD-CTL-005, ARD-OBS-001..003 | Existing H3/H4 recorder through `ControllerCaseContextRecorder` |
| `controller_aggregation`, `controller_conflict` | ARD-CTL-006..008, ARD-GOV-002..005, ARD-PRN-008 | `controller/compliance.py` after candidate aggregation and when conflicts remain |
| `controller_handoff` | ARD-CTL-010/017..018, ARD-GOV-008, ARD-OBS-001..004 | `controller/compliance.py` when the unranked advisory handoff is assembled |

Event details contain identifiers, counts, statuses, and evidence references only. The shared structured serializer redacts sensitive keys before both persistence and logging; no private chain-of-thought or raw specialist payload is recorded.
| ARD-CTL-006..008, ARD-DAT-004..010, ARD-GOV-002..005, ARD-RES-003..006 | `controller/aggregation.py`: validates common and role-specific result envelopes, evidence references, missing/degraded evidence, and both evidence and Operations conflicts; applies deterministic confidence caps | `tests/integration/test_controller_specialist_fanout.py`: malformed reference, failed source, conflicting sources, deterministic escalation, and missing-required-result cases |
| ARD-TST-001..003/005, ARD-RUB-001..004 | Shared synthetic fixtures and integrated foundation scenario | `tests/conftest.py`, `tests/test_synthetic_fixtures.py`, all test files listed above; full result: 74 passed |

## AI-Assisted Iteration Evidence

Implementation followed the accepted OpenSpec proposal, design, spec, and task
sequence. Tests and diagnostics informed corrections before task completion:

- A strict datetime test initially supplied a string; the test fixture was
	corrected to provide a timezone-aware `datetime` object.
- The first invalid-case fixture mutated the shared valid payload; it was
	corrected to copy the input so fixtures remain isolated and deterministic.
- A degraded adapter test exposed a missing warning-contract import; the
	adapter was corrected and the same focused tests rerun successfully.
- Ruff findings were corrected, then the formatter and all configured gates
	were rerun against the final tree.

This is a concise implementation-iteration record, not proof of a human RAPID
review or a human redirection decision. A qualified peer must independently
review the inventory below and record any human corrections or conditions.

## Modified-File Inventory for RAPID Peer Review

- Implementation: `src/aog_recovery/adapters/__init__.py`, `src/aog_recovery/adapters/local.py`, `src/aog_recovery/adapters/protocols.py`, `src/aog_recovery/adk/__init__.py`, `src/aog_recovery/adk/context.py`, `src/aog_recovery/config.py`, `src/aog_recovery/contracts/__init__.py`, `src/aog_recovery/contracts/agent.py`, `src/aog_recovery/contracts/audit.py`, `src/aog_recovery/contracts/base.py`, `src/aog_recovery/contracts/case.py`, `src/aog_recovery/contracts/evidence.py`, `src/aog_recovery/contracts/governance.py`, `src/aog_recovery/contracts/tool.py`, `src/aog_recovery/observability/__init__.py`, `src/aog_recovery/observability/context.py`, `src/aog_recovery/observability/structured.py`, `src/aog_recovery/validation/__init__.py`, `src/aog_recovery/validation/boundaries.py`, `src/aog_recovery/validation/confidence.py`, `src/aog_recovery/validation/human_gate.py`, and `src/aog_recovery/validation/models.py`.
- Tests: `tests/conftest.py`, `tests/adapters/test_local_adapter.py`, `tests/contracts/test_agent_contract.py`, `tests/contracts/test_case_contract.py`, `tests/contracts/test_evidence_contract.py`, `tests/contracts/test_tool_decision_audit_contract.py`, `tests/integration/test_shared_foundation_scenarios.py`, `tests/observability/test_structured_audit.py`, `tests/settings/test_settings.py`, `tests/test_synthetic_fixtures.py`, `tests/validation/test_boundary_validation.py`, `tests/validation/test_confidence_assessment.py`, and `tests/validation/test_human_gate.py`.
- Documentation and workflow: `docs/shared-foundation-contracts.md`, this verification record, and `openspec/changes/shared-aog-recovery-foundation/tasks.md`.

`tests/test_environment.py` predates this change and is included in the full
suite but is not a modified file.

Peer review, reviewer identity, InfoSec/Reference Architecture alignment,
acceptance conditions, and the final RAPID recommendation remain uncompleted
human activities. No approval status is asserted here.

## Synthetic Sponsor-Demo Scenario

Run `uv run pytest tests/integration/test_shared_foundation_scenarios.py -q`.
The deterministic scenario uses a synthetic AOG case and fixture evidence,
exercises unavailable/malformed/stale/partial/conflicting adapter outcomes,
shows low confidence and a material conflict requiring escalation, verifies
case/trace/request IDs in the audit event, and contrasts a pending approval
gate with matching Ops lead plus Maintenance/airworthiness approvals. The
recorded test output is one passing integration test; the final suite includes
it in the 74 passing tests.

No enterprise endpoint, real aircraft record, credential, or operational
write is used. The test demonstrates contract behavior only: humans retain
airworthiness and operational authority, make any Go/No-Go decision, and deliver
the live sponsor presentation and answer questions.