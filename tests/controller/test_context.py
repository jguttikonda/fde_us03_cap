import pytest

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.controller.intake import (
    InMemoryCaseContextStore,
    IntakeStatus,
    validate_controller_intake,
)


def intake_payload(case_id: str, request_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": request_id,
        "case": {
            "case_id": case_id,
            "aircraft_id": "N123AB",
            "event_type": "hydraulic_pump_failure",
            "defect_summary": "Hydraulic pump P-110 failure",
            "location": "MIA",
            "event_at": "2026-10-22T10:00:00Z",
            "created_at": "2026-10-22T10:05:00Z",
            "schema_version": "1.0",
            "trace_context": {
                "trace_id": f"trace-{case_id}",
                "correlation_id": f"corr-{case_id}",
            },
        },
        "failed_part_number": "P-110",
        "affected_flight_numbers": ["FX103"],
        "evaluated_at": "2026-10-22T10:10:00Z",
    }


def validated_intake(case_id: str, request_id: str):
    result = validate_controller_intake(intake_payload(case_id, request_id))
    assert result.status is IntakeStatus.READY
    assert result.intake is not None
    return result.intake


def test_case_context_records_routing_and_correlated_audit_event() -> None:
    context = InMemoryCaseContextStore().start_case(
        validated_intake("AOG-CONTROLLER-001", "req-controller-001")
    )

    assert {item.agent_role for item in context.routing_decisions if item.selected} == {
        AgentRole.MAINTENANCE,
        AgentRole.MATERIALS_LOGISTICS,
        AgentRole.OPERATIONS,
    }
    assert len(context.audit_events) == 1
    event = context.audit_events[0]
    assert event.case_id == context.case_id
    assert event.request_id == context.request_id
    assert event.trace_context == context.trace_context
    assert event.event_type == "controller.intake.accepted"


def test_context_store_keeps_case_data_isolated() -> None:
    store = InMemoryCaseContextStore()
    first = store.start_case(validated_intake("AOG-CONTROLLER-001", "req-001"))
    second = store.start_case(validated_intake("AOG-CONTROLLER-002", "req-002"))

    assert store.get_case(first.case_id) == first
    assert store.get_case(second.case_id) == second
    assert first.case_id != second.case_id
    assert first.audit_events[0].trace_context != second.audit_events[0].trace_context
    assert store.get_case("AOG-UNKNOWN") is None


def test_duplicate_active_case_id_cannot_overwrite_context() -> None:
    store = InMemoryCaseContextStore()
    first = store.start_case(validated_intake("AOG-CONTROLLER-001", "req-001"))

    with pytest.raises(ValueError, match="already active"):
        store.start_case(validated_intake("AOG-CONTROLLER-001", "req-002"))

    assert store.get_case(first.case_id) == first
