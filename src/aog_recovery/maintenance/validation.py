"""Maintenance input validation (ARD-MNT-001..002/007, ARD-DAT-009)."""

from pydantic import ValidationError

from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.maintenance.models import (
    MaintenanceAssessmentInput,
    MaintenanceInputReport,
    MaintenanceInputStatus,
)
from aog_recovery.validation.models import ValidationFinding


def validate_maintenance_input(payload: object) -> MaintenanceInputReport:
    try:
        assessment_input = MaintenanceAssessmentInput.model_validate(payload)
    except ValidationError as error:
        validation_findings = tuple(
            sorted(
                (
                    ValidationFinding(
                        field_path=".".join(str(part) for part in issue["loc"]) or "$",
                        code=issue["type"],
                        message=issue["msg"],
                    )
                    for issue in error.errors()
                ),
                key=lambda finding: (finding.field_path, finding.code, finding.message),
            )
        )
        return MaintenanceInputReport(
            status=MaintenanceInputStatus.REJECTED,
            validated_input=None,
            missing_data=(),
            findings=validation_findings,
        )

    missing_data = set(assessment_input.missing_data)
    if assessment_input.aircraft_metadata is None:
        missing_data.add("aircraft_metadata")
    if assessment_input.work_order is None:
        missing_data.add("work_order")
    elif assessment_input.work_order.estimated_repair_duration_hours is None:
        missing_data.add("work_order.estimated_repair_duration_hours")
    if not assessment_input.maintenance_history:
        missing_data.add("maintenance_history")
    if not assessment_input.engineering_constraints:
        missing_data.add("engineering_constraints")
    if not assessment_input.safety_conditions:
        missing_data.add("safety_conditions")
    if assessment_input.need_by_time is None:
        missing_data.add("need_by_time")
    if (
        any(dependency.required_before_repair for dependency in assessment_input.part_dependencies)
        and assessment_input.parts_ready_at is None
    ):
        missing_data.add("parts_ready_at")

    findings = [
        ValidationFinding(
            field_path=field_path,
            code="missing_evidence",
            message=f"required assessment evidence '{field_path}' is unavailable",
        )
        for field_path in sorted(missing_data)
    ]
    for field_path, evidence_records in _evidence_groups(assessment_input):
        for index, evidence in enumerate(evidence_records):
            if evidence.validity_state is EvidenceValidity.STALE:
                findings.append(
                    ValidationFinding(
                        field_path=f"{field_path}[{index}]",
                        code="stale_evidence",
                        message="evidence is marked stale",
                    )
                )
            elif evidence.validity_state is EvidenceValidity.PARTIAL:
                findings.append(
                    ValidationFinding(
                        field_path=f"{field_path}[{index}]",
                        code="partial_evidence",
                        message="evidence is marked partial",
                    )
                )
            elif evidence.validity_state is EvidenceValidity.CONFLICTING:
                findings.append(
                    ValidationFinding(
                        field_path=f"{field_path}[{index}]",
                        code="conflicting_evidence",
                        message="evidence is marked conflicting",
                    )
                )

    findings.sort(key=lambda finding: (finding.field_path, finding.code, finding.message))
    status = (
        MaintenanceInputStatus.PROVISIONAL
        if missing_data or findings
        else MaintenanceInputStatus.READY
    )
    return MaintenanceInputReport(
        status=status,
        validated_input=assessment_input,
        missing_data=tuple(sorted(missing_data)),
        findings=tuple(findings),
    )


def _evidence_groups(
    assessment_input: MaintenanceAssessmentInput,
) -> tuple[tuple[str, tuple[Evidence, ...]], ...]:
    work_order_evidence = (
        (assessment_input.work_order.evidence,) if assessment_input.work_order is not None else ()
    )
    aircraft_metadata = (
        (assessment_input.aircraft_metadata,)
        if assessment_input.aircraft_metadata is not None
        else ()
    )
    return (
        ("aircraft_metadata", aircraft_metadata),
        ("work_order.evidence", work_order_evidence),
        ("maintenance_history", assessment_input.maintenance_history),
        ("engineering_constraints", assessment_input.engineering_constraints),
        ("safety_conditions", assessment_input.safety_conditions),
    )
