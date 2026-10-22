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
| Historical shared-foundation contract, validation, adapter, settings, audit, fixture, and integration tests | `uv run pytest` | 74 passed at the original foundation verification |
| Lint | `uv run ruff check .` | All checks passed |
| Formatting | `uv run ruff format --check .` | 89 files already formatted |
| Type checking | `uv run mypy src` | Success, no issues in 23 source files |

The test data is synthetic and deterministic. These results validate local
contracts and mocks only; they do not represent live enterprise connectivity,
airworthiness approval, operational execution, sponsor approval, or Go/No-Go.
The 74-test result is a historical foundation baseline, not the current
repository-wide total. Current Controller runtime and suite evidence is kept in
[controller-orchestration-verification.md](controller-orchestration-verification.md).

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
| ARD-TST-001..003/005/007..009, ARD-PRN-001..008, ARD-CTL-006..008/017..018, ARD-OBS-001..004 | Shared synthetic fixtures and integrated foundation scenario | `tests/conftest.py`, `tests/test_synthetic_fixtures.py`, and shared-foundation tests; historical full result: 74 passed |

Controller runtime requirements and lifecycle events are maintained in one
current section in
[controller-orchestration-verification.md](controller-orchestration-verification.md).

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