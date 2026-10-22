# Maintenance Test Traceability

| Requirements | Model / implementation | Test evidence |
|---|---|
| ARD-DAT-001/004..011, ARD-MNT-003..006/009..010 | `MaintenanceAssessmentPayload`, `EngineeringApprovalEvidence`, `RecurringFailureSummary` | `tests/contracts/test_specialist_payloads.py` |
| ARD-MNT-001..002/007, ARD-DAT-009, ARD-SEC-004, ARD-GOV-005 | `MaintenanceAssessmentInput`, `validate_maintenance_input` | `tests/maintenance/test_input_validation.py` |
| ARD-MNT-003..006, ARD-TEC-002/005, ARD-PRN-004..005, ARD-SEC-008 | `MaintenanceAgent`, `MaintenancePromptStage`, shared `AgentResult` | `tests/maintenance/test_agent_pipeline.py::test_maintenance_agent_runs_bounded_stages_and_returns_shared_envelope` |
| ARD-MNT-007, ARD-GOV-002/005, ARD-RES-004 | `MaintenanceInputReport`, `_normalize_payload` | `tests/maintenance/test_agent_pipeline.py::test_provisional_input_stays_partial_and_confidence_is_reduced` |
| ARD-MNT-006, ARD-GOV-006/008, ARD-SEC-008 | `EngineeringApprovalEvidence`, `_to_agent_result` | `tests/maintenance/test_agent_pipeline.py::test_unapproved_repair_is_escalated_without_agent_approval` |
| ARD-MNT-009..010, ARD-DAT-004..006, ARD-MLG-009, ARD-SYS-004, ARD-NFR-003 | `analyze_recurring_failures`, `RecurringFailureSummary` | `tests/maintenance/test_agent_pipeline.py::test_three_in_ninety_p110_history_is_grounded_and_preferred_part_is_requested`; `tests/maintenance/test_failure_history.py` |
| ARD-MNT-004/010, ARD-MLG-005..006, ARD-GOV-005 | `_normalize_payload`, `MaintenanceAssessmentPayload` | `test_return_to_service_uses_parts_ready_then_ground_time_and_need_by`, `test_missing_parts_ready_time_keeps_return_to_service_unknown`, and `test_missing_need_by_keeps_need_by_comparison_unknown` |
| ARD-MNT-008, ARD-GOV-003..005, ARD-RES-006 | Maintenance evidence validator and confidence normalization | `tests/maintenance/test_agent_pipeline.py::test_conflicting_maintenance_evidence_forces_escalation` |
| ARD-MNT-003/005..006, ARD-PRN-001..002, ARD-GOV-008, ARD-SEC-002..003, ARD-TST-005/007 | `MaintenanceAssessmentPayload`, `MaintenanceAgent` | `test_not_feasible_assessment_is_preserved_as_a_domain_result` and `test_maintenance_agent_has_no_approval_or_operational_action_methods` |