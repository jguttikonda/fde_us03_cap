from datetime import UTC, datetime, timedelta

from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.maintenance.models import (
    MaintenanceAssessmentInput,
    MaintenanceInputStatus,
    MaintenancePartDependency,
    MaintenanceWorkOrder,
    WorkOrderStatus,
)
from aog_recovery.maintenance.validation import validate_maintenance_input

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def evidence(evidence_id: str, content: dict[str, object] | None = None) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        source="synthetic-maintenance-system",
        retrieved_at=TIMESTAMP,
        validity_state=EvidenceValidity.CURRENT,
        claim_reference=f"claim-{evidence_id}",
        content=content or {"state": "synthetic"},
    )


def valid_maintenance_input() -> MaintenanceAssessmentInput:
    return MaintenanceAssessmentInput(
        schema_version="1.0",
        case=AogCase(
            case_id="case-synthetic-001",
            aircraft_id="TEST-AIRCRAFT-001",
            event_type="synthetic_defect",
            defect_summary="Synthetic test defect",
            location="TEST-STATION-A",
            event_at=TIMESTAMP,
            created_at=TIMESTAMP,
            schema_version="1.0",
            trace_context=TraceContext(
                trace_id="trace-synthetic-001",
                correlation_id="correlation-synthetic-001",
            ),
        ),
        need_by_time=TIMESTAMP + timedelta(hours=5),
        need_by_evidence_reference="schedule-needby-synthetic-001",
        parts_ready_at=TIMESTAMP,
        parts_readiness_evidence_reference="materials-eta-synthetic-001",
        aircraft_metadata=evidence("aircraft-meta-001", {"aircraft_id": "TEST-AIRCRAFT-001"}),
        work_order=MaintenanceWorkOrder(
            work_order_id="work-order-synthetic-001",
            aircraft_id="TEST-AIRCRAFT-001",
            status=WorkOrderStatus.OPEN,
            required_actions=("synthetic_inspection",),
            estimated_repair_duration_hours=4.0,
            evidence=evidence("work-order-evidence-001"),
        ),
        maintenance_history=(evidence("history-001"),),
        engineering_constraints=(evidence("engineering-001"),),
        safety_conditions=(evidence("safety-001"),),
        part_dependencies=(
            MaintenancePartDependency(
                part_number="P-110",
                required_quantity=1,
                required_before_repair=True,
                evidence_references=("dependency-001",),
            ),
        ),
        missing_data=(),
    )


def test_complete_maintenance_input_is_ready() -> None:
    report = validate_maintenance_input(valid_maintenance_input().model_dump(mode="python"))

    assert report.status is MaintenanceInputStatus.READY
    assert report.missing_data == ()
    assert report.findings == ()


def test_missing_work_order_is_provisional_with_field_finding() -> None:
    payload = valid_maintenance_input().model_dump(mode="python")
    payload["work_order"] = None

    report = validate_maintenance_input(payload)

    assert report.status is MaintenanceInputStatus.PROVISIONAL
    assert "work_order" in report.missing_data
    assert any(
        finding.field_path == "work_order" and finding.code == "missing_evidence"
        for finding in report.findings
    )


def test_missing_work_order_duration_is_provisional() -> None:
    payload = valid_maintenance_input().model_dump(mode="python")
    payload["work_order"]["estimated_repair_duration_hours"] = None

    report = validate_maintenance_input(payload)

    assert report.status is MaintenanceInputStatus.PROVISIONAL
    assert "work_order.estimated_repair_duration_hours" in report.missing_data


def test_unsupported_schema_and_untrusted_extra_field_are_rejected() -> None:
    payload = valid_maintenance_input().model_dump(mode="python")
    payload["schema_version"] = "9.0"

    unsupported = validate_maintenance_input(payload)
    assert unsupported.status is MaintenanceInputStatus.REJECTED
    assert any(finding.field_path == "schema_version" for finding in unsupported.findings)

    payload = valid_maintenance_input().model_dump(mode="python")
    payload["execute_transfer"] = True
    untrusted = validate_maintenance_input(payload)
    assert untrusted.status is MaintenanceInputStatus.REJECTED
    assert any(finding.field_path == "execute_transfer" for finding in untrusted.findings)


def test_aircraft_identity_mismatch_is_rejected() -> None:
    payload = valid_maintenance_input().model_dump(mode="python")
    payload["work_order"]["aircraft_id"] = "TEST-AIRCRAFT-OTHER"

    report = validate_maintenance_input(payload)

    assert report.status is MaintenanceInputStatus.REJECTED
    assert any("aircraft_id" in finding.message for finding in report.findings)


def test_stale_evidence_is_retained_and_makes_input_provisional() -> None:
    payload = valid_maintenance_input().model_dump(mode="python")
    payload["maintenance_history"][0]["validity_state"] = EvidenceValidity.STALE

    report = validate_maintenance_input(payload)

    assert report.status is MaintenanceInputStatus.PROVISIONAL
    assert any(finding.code == "stale_evidence" for finding in report.findings)
