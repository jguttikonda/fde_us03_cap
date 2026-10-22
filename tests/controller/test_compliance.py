import json
from datetime import UTC, datetime
from pathlib import Path

from aog_recovery.controller.candidates import build_recovery_candidates
from aog_recovery.controller.compliance import apply_compliance_gate
from aog_recovery.controller.models import CandidateBuildContext
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
)
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAssessmentInput
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    TraceabilityStatus,
)
from aog_recovery.operations.models import OptionKind

FIXTURE_ROOT = Path("incidents/mock_data")


def candidate_plans(*, unverified: bool = False, missing_eligibility: bool = False):
    document = json.loads(
        (FIXTURE_ROOT / "materials_logistics_agent.json").read_text(encoding="utf-8")
    )
    scenario = next(
        item for item in document["scenarios"] if item["scenario_id"] == "part_available_remote"
    )
    payload = MaterialsLogisticsAssessmentInput.model_validate_json(json.dumps(scenario["input"]))
    assessment = payload.assessment
    if missing_eligibility:
        assessment = assessment.model_copy(update={"part_eligibility": ()})
    elif unverified:
        eligibility = tuple(
            item.model_copy(
                update={
                    "authorization": AuthorizationStatus.UNKNOWN,
                    "traceability": TraceabilityStatus.NOT_VERIFIED,
                }
            )
            for item in assessment.part_eligibility
        )
        assessment = assessment.model_copy(update={"part_eligibility": eligibility})
    context = CandidateBuildContext(
        schema_version="1.0",
        case=payload.case,
        request_id="REQ-COMPLIANCE-1042",
        evaluated_at=datetime(2026, 10, 22, 10, 10, tzinfo=UTC),
        failed_part_number="P-110",
        preferred_replacement_part="P-120",
        estimated_repair_duration_hours=3.0,
        maintenance_evidence_references=("MNT-ETA-1042",),
        materials_assessment=assessment,
    )
    return build_recovery_candidates(context)


def approval(status: ApprovalEvidenceStatus) -> EngineeringApprovalEvidence:
    return EngineeringApprovalEvidence(
        status=status,
        approver_role="maintenance_airworthiness"
        if status is ApprovalEvidenceStatus.APPROVAL_RECORDED
        else None,
        source_reference="APPROVAL-P120-1042"
        if status is ApprovalEvidenceStatus.APPROVAL_RECORDED
        else None,
        recorded_at=datetime(2026, 10, 22, 10, 6, tzinfo=UTC)
        if status is ApprovalEvidenceStatus.APPROVAL_RECORDED
        else None,
    )


def test_missing_engineering_approval_excludes_repair_but_keeps_swap_and_delay() -> None:
    result = apply_compliance_gate(candidate_plans(), approval(ApprovalEvidenceStatus.PENDING))

    assert not any(
        item.option.kind in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
        for item in result.eligible_candidates
    )
    assert {item.option.kind for item in result.eligible_candidates} == {
        OptionKind.SWAP,
        OptionKind.DELAY,
    }
    assert len(result.excluded_options) == 1
    assert any(
        "approval is not recorded" in reason for reason in result.excluded_options[0].reasons
    )


def test_unverified_part_is_excluded_and_never_returned_as_eligible() -> None:
    result = apply_compliance_gate(
        candidate_plans(unverified=True), approval(ApprovalEvidenceStatus.APPROVAL_RECORDED)
    )

    assert len(result.excluded_options) == 1
    reasons = result.excluded_options[0].reasons
    assert "part authorization is not confirmed" in reasons
    assert "part traceability is not verified" in reasons
    assert all(
        item.option.kind not in {OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE}
        for item in result.eligible_candidates
    )


def test_missing_part_eligibility_is_excluded_with_visible_reason() -> None:
    result = apply_compliance_gate(
        candidate_plans(missing_eligibility=True),
        approval(ApprovalEvidenceStatus.APPROVAL_RECORDED),
    )

    assert len(result.excluded_options) == 1
    assert any("evidence is missing" in reason for reason in result.excluded_options[0].reasons)
