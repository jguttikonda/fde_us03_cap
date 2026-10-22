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

## Historical Synthetic Demonstration

This section records the deterministic orchestration demonstration before ranked recommendations were added. It used synthetic AOG cases, fake specialist prompt runners, and local/mock Operations; its result was an advisory, unranked handoff. The archived workflow baseline and 435-test run above remain historical evidence, not verification of the ranked recommendation change below.

## Ranked Recommendation Change Evidence

The active change is [`rank-aog-recovery-recommendations`](../openspec/changes/rank-aog-recovery-recommendations/proposal.md). Its capability specs, design, and task-to-test plan are retained with the change. The requirement-to-test rows below map candidate expansion, deterministic score and cost factors, close-score handling, compliance exclusion, decision-brief contents, degraded evidence, dual approval, audit persistence, and ADK response behavior to focused test functions.

Follow-up verification tasks for terminal `resolved` status, report-level close-score selection, and all-excluded escalation are tracked as tasks 2.4 and 3.4; the active change has 16/16 tasks complete.

The implementation adds `controller/scoring.py`, `controller/ranking.py`, `controller/recommendation.py`, and typed recommendation/decision contracts in `controller/models.py` and `contracts/governance.py`. Focused verification uses `tests/contracts/test_controller_contracts.py`, `tests/contracts/test_tool_decision_audit_contract.py`, `tests/validation/test_human_gate.py`, `tests/integration/test_controller_compliance.py`, `tests/integration/test_controller_workflow.py`, and `tests/integration/test_h3_h4_recorder.py`. The repository-wide test, Ruff, type, format, and strict OpenSpec gates are tracked under task 5.1; results are recorded after that task completes.

## Runtime Scenario Traceability

| Scenario | ARD coverage | Requirement-to-test mapping |
|---|---|---|
| Optional model-backed Operations startup rejects absent/example credentials and keeps configured key material secret | ARD-DEP-001..002, ARD-SEC-006, ARD-NFR-006 | `tests/operations/test_ops_adk_and_demo.py::test_model_backed_adk_startup_rejects_missing_or_placeholder_credential`; `test_configured_model_credential_is_secret_typed_and_excluded_from_output` |
| Proposal Test Case 1: source-backed repair is presented for human review | ARD-TST-006, ARD-CTL-013..016, ARD-GOV-006..008 | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options`; `test_compliant_repair_is_unranked_and_still_requires_human_approval` |
| Proposal Test Case 2: feasible swap retains Operations and evidence details in the Controller report | ARD-OPS-001..004, ARD-CTL-006/013..016, ARD-TST-006 | `tests/integration/test_controller_workflow.py::test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate` |
| Proposal Test Case 5: P-110 recurrence and P-120 preference are exchanged and recorded | ARD-SYS-004, ARD-MNT-009..010, ARD-MLG-009, ARD-OBS-001..004 | `tests/integration/test_specialist_workflow.py::test_both_specialists_complete_synthetic_a2a_with_correlated_audit`; `test_cached_inventory_failure_reaches_materials_h4_and_correlated_exchange` |
| Proposal Test Case 6: 1,200 packages, 900 substitute capacity, priority-first allocation before 17:30, 300 unprotected | ARD-OPS-009, ARD-CTL-019, ARD-TST-006 | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options`; `tests/operations/test_ops_rules.py::test_case_6_swap_capacity_900_with_300_unprotected` |
| Proposal Test Case 7: unauthorized part or unapproved repair is excluded before ranking | ARD-CTL-017, ARD-TST-004/006 | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options`; `test_compliance_gate_excludes_unknown_or_failed_authorization` |
| Proposal Test Case 8: deterministic weighted score explains the cheaper but slower option | ARD-CTL-011..014/019, ARD-TST-004 | `tests/integration/test_controller_compliance.py::test_cost_changes_score_only_through_its_weight_and_scoring_is_reproducible`; `test_scoring_uses_baseline_weights_and_sums_cost_components_once` |
| Unavailable specialist source and Operations timeout preserve structured failures, missing analysis, and pending approval in the decision brief | ARD-RES-002..007, ARD-GOV-005..008, ARD-TST-003/005/009 | `tests/integration/test_controller_workflow.py::test_workflow_honors_omitted_and_unavailable_specialist_routes`; `test_operations_timeout_is_bounded_visible_and_candidate_local` |
| Malformed specialist schema remains a structured Controller failure; missing readiness is retained | ARD-DAT-008..010, ARD-RES-003..006, ARD-TST-002..003/009 | `tests/integration/test_controller_workflow.py::test_malformed_specialist_schema_remains_visible_in_controller_report`; `test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate` |
| Stale evidence remains visible, and Maintenance 3-hour repair versus Operations 7-hour disruption escalates with both evidence references and a pending human gate | ARD-GOV-004..005, ARD-RES-001/006, ARD-TST-006 | `tests/integration/test_controller_workflow.py::test_workflow_preserves_degraded_evidence_and_excludes_unverified_parts` |
| Audit trail preserves H3-before-H4 order, case/trace/evidence correlation, recommendation version linkage, redaction, append-failure state, and excludes private reasoning | ARD-OBS-001..004, ARD-SEC-006..009, ARD-PRN-008, ARD-RES-003..006 | `tests/integration/test_h3_h4_recorder.py::test_recorder_appends_request_before_response_and_correlates_audit`; `test_recorder_rejects_response_before_request_and_has_no_mutating_api`; `test_controller_audit_events_are_correlated_redacted_and_case_isolated`; `tests/integration/test_controller_compliance.py::test_recommendation_audit_events_are_versioned_redacted_and_case_correlated`; `test_recommendation_audit_failure_is_visible_and_escalated`; `tests/observability/test_structured_audit.py::test_sensitive_nested_values_are_redacted_before_serialization` |
| High confidence, degraded/conflicting evidence, and mismatched approvers cannot bypass the human gate | ARD-GOV-001..008, ARD-PRN-001..002/008, ARD-TST-005/007 | `tests/integration/test_controller_compliance.py::test_high_confidence_handoff_still_requires_human_approval`; `test_recommendation_preserves_degradation_conflicts_and_zero_scoreable_status`; `test_human_actions_update_only_advisory_report_state`; `tests/validation/test_human_gate.py::test_required_approvers_must_select_the_same_action_and_option` (audit/human-gate focused run: 50 passed; dependency warning only) |
| Candidate inputs map without inference; malformed or unresolved inputs fail locally | ARD-CTL-006/008/018, ARD-DAT-003..010, ARD-GOV-005 | `tests/integration/test_controller_workflow.py::test_specialist_adapters_preserve_candidate_domain_inputs`; `test_specialist_adapters_keep_invalid_inputs_candidate_local` |
| Operations deadline, timeout metadata, missing analysis, capacity containment, and unaffected candidates | ARD-RES-002..005/007, ARD-CTL-008/018, ARD-OBS-001..003, ARD-NFR-001..002 | `tests/integration/test_controller_workflow.py::test_operations_timeout_is_bounded_visible_and_candidate_local` |
| H3/H4 append failure remains partial and visible | ARD-CTL-005..006, ARD-RES-003..005/007 | `tests/integration/test_controller_workflow.py::test_workflow_keeps_failures_candidate_local_and_records_timeout_and_h3_failure`; `tests/integration/test_h3_h4_recorder.py::test_controller_context_append_failure_is_visible` |
| Cached inventory source failure is reachable through the built ADK inventory tool; stale evidence, primary error, and correlation survive Materials/H4/Controller reporting | ARD-MLG-007, ARD-RES-001/006, ARD-CTL-006..008, ARD-OBS-001..004 | `tests/adapters/test_materials_tools.py::test_adk_inventory_tool_uses_cache_and_preserves_primary_failure`; `tests/integration/test_specialist_workflow.py::test_cached_inventory_failure_reaches_materials_h4_and_correlated_exchange`; `tests/integration/test_controller_workflow.py::test_cached_inventory_failure_reaches_controller_report_and_correlated_audit` |
| Compliance exclusion and conflicting evidence remain visible | ARD-CTL-017..018, ARD-GOV-002..005 | `tests/integration/test_controller_workflow.py::test_workflow_preserves_degraded_evidence_and_excludes_unverified_parts`; `tests/integration/test_controller_compliance.py::test_compliance_gate_excludes_unknown_or_failed_authorization`; `test_conflict_and_handoff_audit_events_are_correlated` |
| Pending human approval is preserved for eligible and degraded handoffs | ARD-GOV-006..008, ARD-PRN-001..002 | `tests/integration/test_controller_workflow.py::test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate`; `tests/integration/test_controller_compliance.py::test_compliant_repair_is_unranked_and_still_requires_human_approval` |
| Human decisions are typed, timezone-aware, bound to the active case/option/version, require both roles for every option, and update advisory status only | ARD-DAT-010..011, ARD-GOV-001..008, ARD-PRN-001..002, ARD-TST-002/005 | `tests/contracts/test_tool_decision_audit_contract.py::test_human_decision_rejects_naive_timestamp_and_empty_reviewer`; `test_human_approval_requires_selected_action_and_option`; `tests/validation/test_human_gate.py::test_both_roles_are_required_for_nonrepair_recommendations_too`; `test_required_approvers_must_select_the_same_action_and_option`; `test_agent_result_and_any_confidence_cannot_bypass_human_gate`; `tests/integration/test_controller_compliance.py::test_human_actions_update_only_advisory_report_state` (asserts terminal `resolved`) |
| Human approval completes the workflow with a terminal resolved report status | ARD-CTL-010, ARD-GOV-006..008, ARD-TST-005 | `tests/integration/test_controller_compliance.py::test_human_actions_update_only_advisory_report_state` |
| Decision brief groups the inclusive 2-point boundary, leaves 2.01-point scores ungrouped, and resolves only matching dual human selection; all-excluded outcome escalates | ARD-CTL-015..017, ARD-GOV-006..008, ARD-TST-004..006 | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options`; `test_decision_brief_close_scores_require_human_selection`; `tests/validation/test_human_gate.py::test_required_approvers_must_select_the_same_action_and_option` |
| Concurrent case failure and lifecycle events remain isolated by trace | ARD-RES-007, ARD-OBS-001..004, ARD-SEC-007/009, ARD-NFR-002 | `tests/integration/test_controller_workflow.py::test_concurrent_workflows_isolate_case_results_and_context_events` |
| ADK invalid output and untrusted input cannot become success or action | ARD-SEC-003..005/008, ARD-GOV-008, ARD-PRN-001..006 | `tests/integration/test_controller_workflow.py::test_adk_boundary_returns_explicit_failure_for_invalid_workflow_output`; `test_adk_boundary_returns_explicit_failure_for_workflow_exception`; `test_adk_boundary_keeps_untrusted_intake_invalid_without_fallback` |
| Least-privilege negative tests reject unauthorized roles, wrong-tool requests, attempted writes, malformed external data, prompt injection, and secret disclosure; adapters expose no operational write surface | ARD-SEC-001..007, ARD-GOV-008, ARD-TST-007 | `tests/adapters/test_local_adapter.py::test_local_adapter_rejects_caller_outside_role_allowlist`; `tests/adapters/test_materials_tools.py::test_source_request_rejects_missing_required_fields_and_write_access`; `tests/operations/test_ops_security_and_gate.py`; `tests/observability/test_structured_audit.py::test_sensitive_nested_values_are_redacted_before_serialization`; `tests/maintenance/test_agent_pipeline.py::test_maintenance_agent_has_no_approval_or_operational_action_methods` (focused run: 38 passed; dependency warnings only) |

## Controller Requirement and Event Evidence

| ARD coverage | Current implementation and control | Verification evidence |
|---|---|---|
| ARD-CTL-001..006/008, ARD-DAT-001..003/009..010, ARD-SEC-003..005 | `controller/intake.py`, `controller/models.py`, `controller/workflow.py`: strict intake, deterministic routing/source-health allowlist, field-level findings, and visible route state | `tests/contracts/test_controller_contracts.py`; `tests/integration/test_controller_workflow.py::test_invalid_workflow_intake_invokes_no_specialist`; `test_workflow_honors_omitted_and_unavailable_specialist_routes` |
| ARD-CTL-018, ARD-DAT-004/012, ARD-GOV-005, ARD-PRN-003 | `controller/candidates.py`: one stable candidate per sourcing offer, later-of-repair/source readiness with both evidence trails, and explicit missing ETA/source/package inputs; M&L adapter narrows the typed request to the selected offer | `tests/contracts/test_controller_contracts.py::test_candidate_construction_expands_sourcing_offers_with_stable_candidate_specific_eta`; `tests/integration/test_controller_workflow.py::test_specialist_adapters_preserve_candidate_domain_inputs` |
| ARD-CTL-011..014/019, ARD-DAT-004..006, ARD-GOV-004..005 | `controller/scoring.py`: fixed weighted aggregation, case-relative normalization, selected USD component sum, and explicit unscored reasons | `tests/contracts/test_controller_contracts.py::test_case_relative_normalization_handles_single_equal_and_opposed_values`; `tests/integration/test_controller_compliance.py::test_scoring_uses_baseline_weights_and_sums_cost_components_once`; `test_individual_impact_package_and_risk_mappings_are_deterministic`; `test_scoring_keeps_missing_cost_and_unknown_risk_unscored`; `test_cost_changes_score_only_through_its_weight_and_scoring_is_reproducible` |
| ARD-CTL-014..015 | `controller/ranking.py`: stable score/ID ordering and inclusive top-two-point selection groups | `tests/contracts/test_controller_contracts.py::test_ranking_is_stable_and_close_score_threshold_is_inclusive`; `test_ranking_handles_ties_and_single_option_without_false_close_selection` |
| ARD-CTL-006/008/018, ARD-DAT-003..010, ARD-RES-003..005/007 | `controller/specialist_adapters.py`, `controller/orchestration.py`: existing role contracts, case/evidence checks, candidate-local structured failures, partial results, and H3/H4 recording | Controller adapter mapping/failure tests and `tests/integration/test_controller_specialist_fanout.py` |
| ARD-CTL-006/018, ARD-OPS-001..009, ARD-RES-002..005/007, ARD-NFR-001..002 | `controller/operations_adapter.py`, `controller/orchestration.py`: configured deadline, bounded worker capacity, per-candidate outcomes and timeout evidence; `OperationsAgent` remains synchronous and unchanged | `test_async_operations_adapter_preserves_deterministic_outcome`; `test_operations_timeout_is_bounded_visible_and_candidate_local`; `tests/integration/test_controller_specialist_fanout.py` |
| ARD-CTL-006..008, ARD-DAT-004..010, ARD-GOV-002..005, ARD-RES-001/003..006 | `controller/aggregation.py`: validates specialist/Operations envelopes and evidence, propagates typed Materials summary warnings/errors, preserves degraded evidence/conflicts, and caps confidence deterministically | `tests/integration/test_controller_specialist_fanout.py`; `test_workflow_preserves_degraded_evidence_and_excludes_unverified_parts`; `test_cached_inventory_failure_reaches_controller_report_and_correlated_audit` |
| ARD-CTL-017, ARD-GOV-001..008, ARD-SEC-001..003/008 | `controller/compliance.py`: deterministic exclusions and pending human approval; no Controller scoring or execution | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options` (including all-excluded escalation); `tests/integration/test_controller_workflow.py::test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate` |
| ARD-CTL-009/016..018, ARD-SYS-005, ARD-GOV-001..005 | `controller/recommendation.py`: consumes only the post-compliance handoff, carries exclusions separately, and composes ranked, unscored, and confidence statuses | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options` |
| ARD-CTL-013..016/018..019, ARD-OPS-009, ARD-DAT-004..006 | `RecoveryDecisionBrief` and `ScoredRecoveryOption`: evidence-linked factors, trade-offs, readiness, route and package allocation, USD cost, risks, assumptions, warnings, and human action | `tests/integration/test_controller_compliance.py::test_recommendation_stage_scores_only_compliance_eligible_options`; `test_decision_brief_close_scores_require_human_selection`; `test_cost_changes_score_only_through_its_weight_and_scoring_is_reproducible`; `tests/integration/test_controller_workflow.py::test_workflow_returns_multi_candidate_unranked_handoff_with_pending_human_gate` |
| ARD-CTL-010, ARD-GOV-006..008 | `apply_human_decisions`: matching dual approval records the terminal `resolved` report status while remaining advisory | `tests/integration/test_controller_compliance.py::test_human_actions_update_only_advisory_report_state` |
| ARD-CTL-008/010/016, ARD-GOV-002..005, ARD-RES-003..006 | `controller/recommendation.py` and `controller/workflow.py`: preserve degraded evidence and structured errors, distinguish escalation/awaiting-data, and suppress the brief on audit append failure | `tests/integration/test_controller_compliance.py::test_recommendation_preserves_degradation_conflicts_and_zero_scoreable_status`; `tests/integration/test_controller_workflow.py::test_workflow_does_not_create_brief_when_handoff_audit_fails` |
| ARD-TEC-002..005, ARD-DAT-001/006/010, ARD-CTL-009..018, ARD-SEC-001..005/008, ARD-GOV-008 | `controller/adk_agent.py`: typed response exposes the versioned decision brief, exclusions, confidence, and human gate; invalid output remains a structured failure with no execution capability | `tests/integration/test_controller_workflow.py::test_adk_agent_binds_versioned_workflow_response_without_model_call`; `test_adk_response_preserves_partial_decision_brief_and_errors`; ADK invalid-output/exception tests |
| ARD-OBS-001..004, ARD-PRN-008, ARD-RES-005/007, ARD-SEC-006..009 | `controller/context.py`, `controller/intake.py`, `controller/orchestration.py`, `controller/compliance.py`: correlated append-only redacted events; evidence and recommendation version references are retained; append failures are visible | `tests/integration/test_h3_h4_recorder.py`; `tests/integration/test_controller_compliance.py::test_recommendation_audit_events_are_versioned_redacted_and_case_correlated`; `test_recommendation_audit_failure_is_visible_and_escalated`; `test_concurrent_workflows_isolate_case_results_and_context_events` |

### Controller Audit Event Map

| Event types | Requirements | Emission point |
|---|---|---|
| `controller_intake_validation`, `controller_routing` | ARD-CTL-001..004, ARD-DAT-001..003/009..010, ARD-SEC-003..005 | `controller/intake.py` after validation and deterministic routing |
| `specialist_invocation`, `specialist_result`, `specialist_timeout`, `specialist_failure` | ARD-CTL-006/008/018, ARD-RES-002..005/007 | `controller/orchestration.py` around bounded specialist calls |
| `operations_invocation`, `operations_result`, `operations_failure`, `operations_timeout` | ARD-CTL-006/018, ARD-OPS-001..009, ARD-RES-002..005 | `controller/orchestration.py` around the bounded Operations adapter |
| `peer_exchange` | ARD-SYS-004, ARD-CTL-005, ARD-OBS-001..003 | H3/H4 recorder through `ControllerCaseContextRecorder` |
| `controller_aggregation`, `controller_conflict` | ARD-CTL-006..008, ARD-GOV-002..005, ARD-PRN-008 | `controller/compliance.py` after aggregation and when conflicts remain |
| `controller_handoff` | ARD-CTL-010/017..018, ARD-GOV-008, ARD-OBS-001..004 | `controller/compliance.py` when the unranked handoff is assembled |
| `controller_option_scored`, `controller_option_unscored`, `controller_option_excluded`, `controller_recommendation`, `controller_escalation` | ARD-CTL-009..019, ARD-GOV-001..005, ARD-PRN-008, ARD-OBS-001..004 | `controller/recommendation.py` after deterministic scoring and report assembly |
| `human_decision` | ARD-GOV-006..008, ARD-PRN-001..002/008, ARD-OBS-001..004 | `controller/recommendation.py` after case/version/option validation; the event is retained before gate state changes |

Event details contain identifiers, counts, statuses, decision action, reviewer,
rationale, recommendation version, and evidence references. The shared
serializer redacts sensitive keys; raw specialist payloads and private
chain-of-thought are not recorded.

## Offline Controller Demo Evidence

The Controller's offline entry point is `uv run python -m aog_recovery.controller.demo`.
It runs happy repair, cache-degraded inventory, the 3h/7h time conflict, and close-score
human-selection scenarios through deterministic Controller aggregation and recommendation
logic with local synthetic Operations adapters. It makes no model or network call and
reports no operational action. Focused evidence: `tests/integration/test_controller_demo.py`
(`uv run pytest tests/integration/test_controller_demo.py -q`: 10 passed).

## Security Scan Evidence

Environment: Windows, Python 3.14.7, uv 0.12.21. Bandit 1.9.4 and pip-audit
2.10.1 are locked in the `dev` dependency group. Gitleaks 8.30.1 is the
installed secret scanner.

| Tool | Command | Result |
|---|---|---|
| Bandit 1.9.4 | `uv run bandit -r src -ll` | No medium or high findings across 10,110 source lines. |
| Bandit 1.9.4 | `uv run bandit -r src -l` | Seven low `B101` assert-use notices: five in Controller scoring, one in Operations, and one in boundary validation. These follow explicit validation/guard conditions and remain listed for human review; no security finding was suppressed. |
| pip-audit 2.10.1 | `uv export --locked --format requirements-txt --no-hashes --no-emit-project --output-file "$env:TEMP\fde-us03-cap-dependencies.txt"`, then `uv run pip-audit --skip-editable -r "$env:TEMP\fde-us03-cap-dependencies.txt"` | No known vulnerabilities in the locked third-party dependencies. `pip-audit --locked .` does not recognize `uv.lock`, so the lock was exported before audit. |
| Gitleaks 8.30.1 | `gitleaks dir . --redact --no-banner` | 250 matches, all in ignored `.venv` package sources (247 generic-key and 3 private-key rules); no project-owned file was reported. Separate scans of `src`, `tests`, `docs`, `openspec`, `.github`, `adk_agents`, `incidents`, and root files found no leaks. |
| Gitleaks 8.30.1 | `gitleaks git . --log-opts="--no-textconv" --redact --no-banner` | 39 commits scanned; no leaks. |

Unverified: Gitleaks does not inspect the binary DOCX/PDF contents in the
working tree. The history scan disables Git textconv so it does not depend on
the unavailable `docx2txt` helper. Binary-document content remains a manual
review item. The ignored `.venv` matches are third-party/generated source, not
repository-owned credentials.

## Ranked Recommendation Verification Results

Environment: Windows, Python 3.14.7, pytest 9.1.1. Final checks for
`rank-aog-recovery-recommendations`:

| Command | Result |
|---|---|
| `uv run pytest --cov=aog_recovery --cov-report=term` | 463 passed; 93% total coverage |
| Focused Controller contracts, scoring, compliance, workflow, human gate, audit, and ADK tests | 124 passed |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 202 files already formatted |
| `uv run mypy src` | Success; no issues in 67 source files |
| `openspec validate --changes "rank-aog-recovery-recommendations" --strict` | Valid; no issues |

The full test run reported two dependency warnings: a `google.genai`
deprecated internal alias and Google ADK's experimental `PLUGGABLE_AUTH`
feature warning. No project test failed. These automated results are not a
peer-review, RAPID, Go/No-Go, sponsor, operational, or airworthiness approval.

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

### Ranked Recommendation Change Iteration

- Candidate data allowed multiple sourcing offers but supplied only one shared repair ETA. The user clarified that each offer must have a stable candidate and readiness must use the later of repair readiness and that offer's ETA; the design and tests were updated to preserve both evidence trails.
- Contract tests exposed two distinct `SourcingMethod` enums across Materials & Logistics and Operations. The implementation uses the shared readiness enum for candidate handoff and filters each M&L request to its selected offer.
- Workflow tests showed that an unranked handoff may be provisional at 0.69 while complete numeric factors remain scoreable. Scoring now keeps scoreability separate from confidence and preserves the provisional gate.
- Tests caught a prior ADK assertion that forbade every `rank` and `score` field; it was narrowed to forbid operational execution fields while allowing the newly specified typed report.
- Strict mypy identified optional specialist-result narrowing, enum export, and typed-assumption issues; these were fixed without suppressions. The full test and static-check results above were rerun after correction.
- Human approval and audit-failure tests confirm that decisions remain tied to the active report version and that failed decision persistence leaves approval pending.

This iteration record documents AI assistance and human direction; it is not a human peer-review result.

## Historical Modified-File Inventory

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

## Prior Hardening Change Deferred Work and Human Decisions (Historical)

This capability stops before weighted scoring, ranking, close-score handling, final recommendation prose, and decision-brief rendering (ARD-CTL-009/011..016/019); those capabilities are deferred to the later `rank-aog-recovery-options` change. Human decision collection remains separate, and every operational and airworthiness decision requires the authorized human roles. No agent executes a booking, purchase, transfer, dispatch, delay, aircraft assignment, or other operational action.

RAPID peer review, Go/No-Go, sponsor delivery and live Q&A, and deployment readiness also remain human/project responsibilities (ARD-TEC-020, ARD-RUB-005..011, ARD-DEP-001 onward). The selected follow-on name is `rank-aog-recovery-options`; that future change does not transfer operational or airworthiness approval away from the authorized people.