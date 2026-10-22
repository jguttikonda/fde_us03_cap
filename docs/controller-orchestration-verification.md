# Controller Runtime Integration Verification Evidence

## Historical Verification Baseline

The following run belongs to the original `orchestrate-aog-recovery-cases`
change (2026-10-21); it is not the current hardening-change result.

| Command | Result |
|---|---|
| `uv run pytest` | 424 passed in 6.81s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 190 files already formatted |
| `uv run mypy src` | Success, no issues in 62 source files |

The original run reported two dependency warnings, neither from project code:

- `google.genai.types`: `_UnionGenericAlias` is deprecated and scheduled for removal in Python 3.17.
- `google.adk.features._feature_decorator`: experimental `FeatureName.PLUGGABLE_AUTH` is enabled.

## Current Verification Run

Environment: Windows, Python 3.14.7, pytest 9.1.1. Commands were run from the repository root on 2026-10-21 after the hardening changes.

| Command | Result |
|---|---|
| `uv run pytest` | 435 passed in 9.68s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 192 files already formatted |
| `uv run mypy src` | Success, no issues in 64 source files |

Pytest reported two dependency warnings, neither from project code: the
`google.genai.types` `_UnionGenericAlias` deprecation for Python 3.17 and the
experimental ADK `PLUGGABLE_AUTH` feature warning. No project test failed.

## Synthetic Demonstration

Run `uv run pytest tests/integration/test_controller_workflow.py -q` for the deterministic orchestration demonstration. The current module contains 14 tests and uses synthetic AOG cases, fake specialist prompt runners, and local/mock Operations. It covers candidate adapter mapping and failures, a bounded real wait timeout, ADK output validation, concurrent case isolation, H3/H4 append failure, compliance exclusion, conflicts, and the pending human gate. The original archived workflow baseline had 5 tests; the current module is included in the 435-test full-suite result above. No live model, network, airline source, or operational write is used. Results remain advisory and unranked.

## Runtime Scenario Traceability

| Scenario | ARD coverage | Requirement-to-test mapping |
|---|---|---|
| Candidate inputs map without inference; malformed or unresolved inputs fail locally | ARD-CTL-006/008/018, ARD-DAT-003..010, ARD-GOV-005 | `tests/integration/test_controller_workflow.py::test_specialist_adapters_preserve_candidate_domain_inputs`; `test_specialist_adapters_keep_invalid_inputs_candidate_local` |
| Operations deadline, timeout metadata, missing analysis, capacity containment, and unaffected candidates | ARD-RES-002..005/007, ARD-CTL-008/018, ARD-OBS-001..003, ARD-NFR-001..002 | `tests/integration/test_controller_workflow.py::test_operations_timeout_is_bounded_visible_and_candidate_local` |
| H3/H4 append failure remains partial and visible | ARD-CTL-005..006, ARD-RES-003..005/007 | `tests/integration/test_controller_workflow.py::test_workflow_keeps_failures_candidate_local_and_records_timeout_and_h3_failure`; `tests/integration/test_h3_h4_recorder.py::test_controller_context_append_failure_is_visible` |
| Compliance exclusion and conflicting evidence remain visible | ARD-CTL-017..018, ARD-GOV-002..005 | `tests/integration/test_controller_workflow.py::test_workflow_preserves_degraded_evidence_and_excludes_unverified_parts`; `tests/integration/test_controller_compliance.py::test_compliance_gate_excludes_unknown_or_failed_authorization`; `test_conflict_and_handoff_audit_events_are_correlated` |
| Pending human approval is preserved for eligible and degraded handoffs | ARD-GOV-006..008, ARD-PRN-001..002 | `tests/integration/test_controller_workflow.py::test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate`; `tests/integration/test_controller_compliance.py::test_compliant_repair_is_unranked_and_still_requires_human_approval` |
| Concurrent case failure and lifecycle events remain isolated by trace | ARD-RES-007, ARD-OBS-001..004, ARD-SEC-007/009, ARD-NFR-002 | `tests/integration/test_controller_workflow.py::test_concurrent_workflows_isolate_case_results_and_context_events` |
| ADK invalid output and untrusted input cannot become success or action | ARD-SEC-003..005/008, ARD-GOV-008, ARD-PRN-001..006 | `tests/integration/test_controller_workflow.py::test_adk_boundary_returns_explicit_failure_for_invalid_workflow_output`; `test_adk_boundary_returns_explicit_failure_for_workflow_exception`; `test_adk_boundary_keeps_untrusted_intake_invalid_without_fallback` |

## Controller Requirement and Event Evidence

| ARD coverage | Current implementation and control | Verification evidence |
|---|---|---|
| ARD-CTL-001..006/008, ARD-DAT-001..003/009..010, ARD-SEC-003..005 | `controller/intake.py`, `controller/models.py`, `controller/workflow.py`: strict intake, deterministic routing/source-health allowlist, field-level findings, and visible route state | `tests/contracts/test_controller_contracts.py`; `tests/integration/test_controller_workflow.py::test_invalid_workflow_intake_invokes_no_specialist`; `test_workflow_honors_omitted_and_unavailable_specialist_routes` |
| ARD-CTL-018, ARD-DAT-012, ARD-GOV-005, ARD-PRN-003 | `controller/candidates.py`: stable candidate identity and explicit missing readiness/sourcing/package-load values | `tests/contracts/test_controller_contracts.py`: repeatable candidate IDs and absent unsupported inputs |
| ARD-CTL-006/008/018, ARD-DAT-003..010, ARD-RES-003..005/007 | `controller/specialist_adapters.py`, `controller/orchestration.py`: existing role contracts, case/evidence checks, candidate-local structured failures, partial results, and H3/H4 recording | Controller adapter mapping/failure tests and `tests/integration/test_controller_specialist_fanout.py` |
| ARD-CTL-006/018, ARD-OPS-001..009, ARD-RES-002..005/007, ARD-NFR-001..002 | `controller/operations_adapter.py`, `controller/orchestration.py`: configured deadline, bounded worker capacity, per-candidate outcomes and timeout evidence; `OperationsAgent` remains synchronous and unchanged | `test_async_operations_adapter_preserves_deterministic_outcome`; `test_operations_timeout_is_bounded_visible_and_candidate_local`; `tests/integration/test_controller_specialist_fanout.py` |
| ARD-CTL-006..008, ARD-DAT-004..010, ARD-GOV-002..005, ARD-RES-003..006 | `controller/aggregation.py`: validates specialist/Operations envelopes and evidence, preserves degraded evidence/conflicts, and caps confidence deterministically | `tests/integration/test_controller_specialist_fanout.py`; `test_workflow_preserves_degraded_evidence_and_excludes_unverified_parts` |
| ARD-CTL-017, ARD-GOV-001..008, ARD-SEC-001..003/008 | `controller/compliance.py`: deterministic exclusions and pending human approval; no Controller scoring or execution | `tests/integration/test_controller_compliance.py`; `test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate` |
| ARD-TEC-002..005, ARD-DAT-001/006/010, ARD-SEC-003..005/008, ARD-GOV-008 | `controller/adk_agent.py`: versioned response envelope, deterministic output validation, structured failure, and ADK direct tool return | ADK boundary tests in `tests/integration/test_controller_workflow.py` |
| ARD-OBS-001..004, ARD-PRN-008, ARD-RES-005/007, ARD-SEC-006..009 | `controller/context.py`, `controller/intake.py`, `controller/orchestration.py`, `controller/compliance.py`: correlated append-only redacted events; append failures are visible | `tests/integration/test_h3_h4_recorder.py`; `tests/integration/test_controller_compliance.py`; `test_concurrent_workflows_isolate_case_results_and_context_events` |

### Controller Audit Event Map

| Event types | Requirements | Emission point |
|---|---|---|
| `controller_intake_validation`, `controller_routing` | ARD-CTL-001..004, ARD-DAT-001..003/009..010, ARD-SEC-003..005 | `controller/intake.py` after validation and deterministic routing |
| `specialist_invocation`, `specialist_result`, `specialist_timeout`, `specialist_failure` | ARD-CTL-006/008/018, ARD-RES-002..005/007 | `controller/orchestration.py` around bounded specialist calls |
| `operations_invocation`, `operations_result`, `operations_failure`, `operations_timeout` | ARD-CTL-006/018, ARD-OPS-001..009, ARD-RES-002..005 | `controller/orchestration.py` around the bounded Operations adapter |
| `peer_exchange` | ARD-SYS-004, ARD-CTL-005, ARD-OBS-001..003 | H3/H4 recorder through `ControllerCaseContextRecorder` |
| `controller_aggregation`, `controller_conflict` | ARD-CTL-006..008, ARD-GOV-002..005, ARD-PRN-008 | `controller/compliance.py` after aggregation and when conflicts remain |
| `controller_handoff` | ARD-CTL-010/017..018, ARD-GOV-008, ARD-OBS-001..004 | `controller/compliance.py` when the unranked handoff is assembled |

Event details contain identifiers, counts, statuses, and evidence references
only. The shared serializer redacts sensitive keys; raw specialist payloads and
private chain-of-thought are not recorded.

## AI-Assisted Iteration Record

- Strict Pydantic fixtures initially supplied enum values as strings. The contract tests exposed the strict-boundary mismatch; fixtures were changed to use typed enum values.
- Candidate tests exposed the missing failed-part identifier needed for H3/H4. Repair candidates now preserve it as explicit missing data instead of inferring a part number.
- The high-confidence compliance fixture initially received a 0.69 cap because its aircraft ID did not match the deterministic Operations schedule. The fixture was corrected to use the schedule's synthetic aircraft identity; the approval-bypass test then exercised confidence at or above 0.70 while the gate remained pending.
- Recorder and audit integration tests exposed event-order assumptions and patch-placement defects. The assertions were narrowed to distinguish general lifecycle events from H3/H4 request/response records, and the same focused tests were rerun after each correction.
- The original orchestration verification identified that recorded routing was not enforced during fan-out. The archived change now passes the route through the workflow, suppresses omitted/unavailable specialist calls, and retains route/source-health state. This hardening change begins after that routed invocation boundary.
- Ruff and mypy findings were corrected before the final repository-wide gates. Full outputs are summarized above.
- Typed specialist adapters preserve the existing domain APIs; prompt-runner assertions exposed fixture aircraft-identity and JSON evidence-shape issues, which were corrected without adding inferred values or changing specialist behavior.
- The Operations wait test confirmed that a timed-out synchronous worker may continue running. The adapter retains its bounded slot until worker completion, rejects extra work at capacity, and exposes the timeout and missing analysis in the candidate result.
- ADK package inspection confirmed `ToolContext.actions.skip_summarization` is the direct-return control. The response path now validates the workflow envelope and returns explicit structured failures without model summarization.
- Concurrent case tests use a gate to prove both workflows overlap before one case's specialist failure; separate handoffs, candidate IDs, and event trace contexts remain isolated.

This is inspectable development evidence, not a human peer review or approval. It does not claim a RAPID recommendation, Go/No-Go decision, or sponsor acceptance.

## Modified-File Inventory

Implementation:

- `src/aog_recovery/config.py`
- `src/aog_recovery/controller/adk_agent.py`
- `src/aog_recovery/controller/models.py`
- `src/aog_recovery/controller/operations_adapter.py`
- `src/aog_recovery/controller/orchestration.py`
- `src/aog_recovery/controller/specialist_adapters.py`
- `src/aog_recovery/controller/workflow.py`
- `.env.example`

Tests:

- `tests/integration/test_controller_specialist_fanout.py`
- `tests/integration/test_controller_workflow.py`
- `tests/integration/test_specialist_workflow.py`
- `tests/settings/test_settings.py`

Documentation and tracking:

- `docs/controller-orchestration-verification.md`
- `docs/shared-foundation-verification.md`
- `openspec/changes/harden-controller-orchestration/specs/controller-runtime-integration/spec.md`
- `openspec/changes/harden-controller-orchestration/tasks.md`

Environment template: `.env.example`.

Routing/source-health enforcement remains owned by the archived `orchestrate-aog-recovery-cases` change; this hardening change does not alter that scope.

## Deferred Work and Human Decisions

This capability stops before weighted scoring, ranking, close-score handling, final recommendation prose, and decision-brief rendering (ARD-CTL-009/011..016/019); those capabilities are deferred to the later `rank-aog-recovery-options` change. Human decision collection remains separate, and every operational and airworthiness decision requires the authorized human roles. No agent executes a booking, purchase, transfer, dispatch, delay, aircraft assignment, or other operational action.

RAPID peer review, Go/No-Go, sponsor delivery and live Q&A, and deployment readiness also remain human/project responsibilities (ARD-TEC-020, ARD-RUB-005..011, ARD-DEP-001 onward). The selected follow-on name is `rank-aog-recovery-options`; that future change does not transfer operational or airworthiness approval away from the authorized people.