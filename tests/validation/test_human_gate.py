from datetime import UTC, datetime

import pytest

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole
from aog_recovery.contracts.governance import (
    HumanDecisionRecord,
    HumanDecisionType,
    ReviewerRole,
)
from aog_recovery.validation.human_gate import (
    HumanGateStatus,
    assess_human_gate,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def decision(
    reviewer_role: ReviewerRole,
    outcome: HumanDecisionType = HumanDecisionType.APPROVE,
    recommendation_version: str = "recommendation-v1",
) -> HumanDecisionRecord:
    return HumanDecisionRecord(
        schema_version="1.0",
        decision_id=f"decision-{reviewer_role.value}",
        case_id="case-001",
        decision=outcome,
        selected_action="repair",
        selected_option_id="option-001",
        reviewer_id=f"reviewer-{reviewer_role.value}",
        reviewer_role=reviewer_role,
        decided_at=TIMESTAMP,
        rationale="Synthetic test rationale",
        recommendation_version=recommendation_version,
    )


def test_both_authorized_roles_are_required_for_repair_approval() -> None:
    outcome = assess_human_gate(
        decisions=(decision(ReviewerRole.OPS_LEAD),),
        case_id="case-001",
        recommendation_version="recommendation-v1",
    )

    assert outcome.status is HumanGateStatus.PENDING
    assert outcome.approved_roles == (ReviewerRole.OPS_LEAD,)
    assert outcome.findings[0].code == "missing_approval_role"


def test_matching_dual_role_approvals_complete_gate() -> None:
    outcome = assess_human_gate(
        decisions=(
            decision(ReviewerRole.OPS_LEAD),
            decision(ReviewerRole.MAINTENANCE_AIRWORTHINESS),
        ),
        case_id="case-001",
        recommendation_version="recommendation-v1",
        valid_option_ids=("option-001",),
    )

    assert outcome.status is HumanGateStatus.APPROVED
    assert outcome.findings == ()


@pytest.mark.parametrize(
    ("decision_type", "expected_status"),
    [
        (HumanDecisionType.REJECT, HumanGateStatus.REJECTED),
        (HumanDecisionType.ESCALATE, HumanGateStatus.ESCALATION_REQUIRED),
        (HumanDecisionType.REQUEST_INFORMATION, HumanGateStatus.INFORMATION_REQUIRED),
    ],
)
def test_nonapproval_human_decisions_do_not_approve(
    decision_type: HumanDecisionType, expected_status: HumanGateStatus
) -> None:
    outcome = assess_human_gate(
        decisions=(decision(ReviewerRole.OPS_LEAD, decision_type),),
        case_id="case-001",
        recommendation_version="recommendation-v1",
    )

    assert outcome.status is expected_status


def test_stale_recommendation_decision_is_not_counted() -> None:
    outcome = assess_human_gate(
        decisions=(decision(ReviewerRole.OPS_LEAD, recommendation_version="recommendation-v0"),),
        case_id="case-001",
        recommendation_version="recommendation-v1",
    )

    assert outcome.status is HumanGateStatus.PENDING
    assert any(finding.code == "stale_recommendation_version" for finding in outcome.findings)


def test_decision_for_option_outside_active_report_is_not_counted() -> None:
    outcome = assess_human_gate(
        decisions=(decision(ReviewerRole.OPS_LEAD),),
        case_id="case-001",
        recommendation_version="recommendation-v1",
        valid_option_ids=("option-002",),
    )

    assert outcome.status is HumanGateStatus.PENDING
    assert any(finding.code == "unknown_selected_option" for finding in outcome.findings)


@pytest.mark.parametrize("confidence", (0.49, 0.69, 0.99))
def test_agent_result_and_any_confidence_cannot_bypass_human_gate(confidence: float) -> None:
    result = AgentResult(
        schema_version="1.0",
        agent_role=AgentRole.CONTROLLER,
        status=AgentResultStatus.COMPLETE,
        summary="Synthetic high-confidence result",
        confidence=confidence,
        assumptions=(),
        evidence_references=(),
        role_payload={"recommendation": "option-001"},
    )

    outcome = assess_human_gate(
        decisions=(),
        case_id="case-001",
        recommendation_version="recommendation-v1",
    )

    assert result.confidence == confidence
    assert outcome.status is HumanGateStatus.PENDING
    assert outcome.approved_roles == ()


def test_both_roles_are_required_for_nonrepair_recommendations_too() -> None:
    operations_only = assess_human_gate(
        decisions=(decision(ReviewerRole.OPS_LEAD),),
        case_id="case-001",
        recommendation_version="recommendation-v1",
        valid_option_ids=("option-001",),
    )
    dual_approval = assess_human_gate(
        decisions=(
            decision(ReviewerRole.OPS_LEAD).model_copy(update={"selected_action": "swap"}),
            decision(ReviewerRole.MAINTENANCE_AIRWORTHINESS).model_copy(
                update={"selected_action": "swap"}
            ),
        ),
        case_id="case-001",
        recommendation_version="recommendation-v1",
        valid_option_ids=("option-001",),
    )

    assert operations_only.status is HumanGateStatus.PENDING
    assert operations_only.required_roles == (
        ReviewerRole.OPS_LEAD,
        ReviewerRole.MAINTENANCE_AIRWORTHINESS,
    )
    assert dual_approval.status is HumanGateStatus.APPROVED


def test_required_approvers_must_select_the_same_action_and_option() -> None:
    outcome = assess_human_gate(
        decisions=(
            decision(ReviewerRole.OPS_LEAD),
            decision(ReviewerRole.MAINTENANCE_AIRWORTHINESS).model_copy(
                update={"selected_option_id": "option-002"}
            ),
        ),
        case_id="case-001",
        recommendation_version="recommendation-v1",
        valid_option_ids=("option-001", "option-002"),
    )

    assert outcome.status is HumanGateStatus.PENDING
    assert any(finding.code == "approval_scope_mismatch" for finding in outcome.findings)
