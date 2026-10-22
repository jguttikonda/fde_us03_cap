from enum import StrEnum

from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.governance import (
    HumanDecisionRecord,
    HumanDecisionType,
    ReviewerRole,
)
from aog_recovery.validation.models import ValidationFinding


class HumanGateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATION_REQUIRED = "escalation_required"
    INFORMATION_REQUIRED = "information_required"


class HumanGateAssessment(ContractModel):
    status: HumanGateStatus
    required_roles: tuple[ReviewerRole, ...]
    approved_roles: tuple[ReviewerRole, ...]
    findings: tuple[ValidationFinding, ...]


def assess_human_gate(
    decisions: tuple[HumanDecisionRecord, ...],
    case_id: str,
    recommendation_version: str,
    valid_option_ids: tuple[str, ...] | None = None,
) -> HumanGateAssessment:
    required_roles = (ReviewerRole.OPS_LEAD, ReviewerRole.MAINTENANCE_AIRWORTHINESS)
    matching_decisions: list[HumanDecisionRecord] = []
    findings: list[ValidationFinding] = []

    for index, decision in enumerate(decisions):
        if decision.case_id != case_id:
            findings.append(
                ValidationFinding(
                    field_path=f"decisions[{index}].case_id",
                    code="case_id_mismatch",
                    message="decision belongs to a different case",
                )
            )
        elif decision.recommendation_version != recommendation_version:
            findings.append(
                ValidationFinding(
                    field_path=f"decisions[{index}].recommendation_version",
                    code="stale_recommendation_version",
                    message="decision does not match the active recommendation version",
                )
            )
        elif (
            valid_option_ids is not None
            and decision.selected_option_id is not None
            and decision.selected_option_id not in valid_option_ids
        ):
            findings.append(
                ValidationFinding(
                    field_path=f"decisions[{index}].selected_option_id",
                    code="unknown_selected_option",
                    message="decision selects an option outside the active recommendation",
                )
            )
        else:
            matching_decisions.append(decision)

    approved_by_role = {
        decision.reviewer_role
        for decision in matching_decisions
        if decision.decision is HumanDecisionType.APPROVE
    }
    approved_roles = tuple(role for role in required_roles if role in approved_by_role)
    decision_types = {decision.decision for decision in matching_decisions}

    if HumanDecisionType.REJECT in decision_types:
        status = HumanGateStatus.REJECTED
    elif HumanDecisionType.ESCALATE in decision_types:
        status = HumanGateStatus.ESCALATION_REQUIRED
    elif HumanDecisionType.REQUEST_INFORMATION in decision_types:
        status = HumanGateStatus.INFORMATION_REQUIRED
    elif findings:
        status = HumanGateStatus.PENDING
    else:
        missing_roles = tuple(role for role in required_roles if role not in approved_by_role)
        if missing_roles:
            findings.extend(
                ValidationFinding(
                    field_path="decisions",
                    code="missing_approval_role",
                    message=f"approval from '{role.value}' is required",
                )
                for role in missing_roles
            )
            status = HumanGateStatus.PENDING
        else:
            approvals = [
                decision
                for decision in matching_decisions
                if decision.decision is HumanDecisionType.APPROVE
                and decision.reviewer_role in required_roles
            ]
            decision_scopes = {
                (decision.selected_action, decision.selected_option_id) for decision in approvals
            }
            missing_selection = any(
                decision.selected_action is None or decision.selected_option_id is None
                for decision in approvals
            )
            if missing_selection:
                findings.append(
                    ValidationFinding(
                        field_path="decisions",
                        code="missing_approval_selection",
                        message="approval must identify its action and selected option",
                    )
                )
                status = HumanGateStatus.PENDING
            elif len(decision_scopes) > 1:
                findings.append(
                    ValidationFinding(
                        field_path="decisions",
                        code="approval_scope_mismatch",
                        message="required approvers must approve the same action and option",
                    )
                )
                status = HumanGateStatus.PENDING
            else:
                status = HumanGateStatus.APPROVED

    return HumanGateAssessment(
        status=status,
        required_roles=required_roles,
        approved_roles=approved_roles,
        findings=tuple(findings),
    )
