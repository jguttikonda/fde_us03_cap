from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel
from test_input_validation import valid_maintenance_input

from aog_recovery.contracts.agent import AgentResultStatus, AgentRole
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.maintenance.agent import (
    PROMPT_A_GROUNDING,
    PROMPT_B_REASONING,
    PROMPT_C_VALIDATION,
    MaintenanceAgent,
    MaintenanceGroundingOutput,
    MaintenancePromptStage,
    MaintenanceReasoningOutput,
)
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentInput,
    MaintenanceAssessmentPayload,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RepairabilityStatus,
    RootCauseEvidence,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class FakePromptRunner:
    def __init__(self, outputs: tuple[BaseModel | dict[str, object], ...]) -> None:
        self.outputs = list(outputs)
        self.stages: list[str] = []
        self.instructions: list[str] = []
        self.payloads: list[dict[str, object]] = []

    async def run_stage(
        self,
        stage: MaintenancePromptStage,
        payload: dict[str, object],
    ) -> dict[str, object]:
        assert payload
        self.payloads.append(payload)
        self.stages.append(stage.value)
        self.instructions.append(
            {
                MaintenancePromptStage.EVIDENCE_GROUNDING: PROMPT_A_GROUNDING,
                MaintenancePromptStage.TECHNICAL_REASONING: PROMPT_B_REASONING,
                MaintenancePromptStage.OUTPUT_VALIDATION: PROMPT_C_VALIDATION,
            }[stage]
        )
        output = self.outputs.pop(0)
        return output.model_dump(mode="python") if isinstance(output, BaseModel) else output


def final_payload(
    assessment_input: MaintenanceAssessmentInput,
    *,
    approval_status: ApprovalEvidenceStatus = ApprovalEvidenceStatus.APPROVAL_RECORDED,
    confidence: float = 0.82,
) -> MaintenanceAssessmentPayload:
    work_order = assessment_input.work_order
    evidence_reference = (
        work_order.evidence.evidence_id if work_order is not None else "history-001"
    )
    approval_reference = next(
        (
            evidence.evidence_id
            for evidence in (
                *assessment_input.safety_conditions,
                *assessment_input.engineering_constraints,
            )
        ),
        evidence_reference,
    )
    return MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=(
            RepairabilityStatus.FEASIBLE
            if approval_status is ApprovalEvidenceStatus.APPROVAL_RECORDED
            else RepairabilityStatus.UNCERTAIN
        ),
        root_cause=RootCauseEvidence(
            category="synthetic_hydraulic_failure",
            confidence=confidence,
            evidence_references=(evidence_reference,),
        ),
        recurring_failure=None,
        preferred_replacement_part=None,
        preferred_replacement_evidence_references=(),
        required_actions=("synthetic_inspection",),
        estimated_ground_time_hours=4.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("125.00"),
        need_by_time=TIMESTAMP,
        parts_ready_at=TIMESTAMP,
        return_to_service_time=TIMESTAMP,
        meets_need_by_time=True,
        eta_confidence=confidence,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.LOW,
            parts_dependency_risk=MaintenanceRiskLevel.LOW,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=approval_status,
            approver_role=(
                "maintenance_airworthiness_authority"
                if approval_status is ApprovalEvidenceStatus.APPROVAL_RECORDED
                else None
            ),
            source_reference=(
                approval_reference
                if approval_status is ApprovalEvidenceStatus.APPROVAL_RECORDED
                else None
            ),
            recorded_at=(
                TIMESTAMP if approval_status is ApprovalEvidenceStatus.APPROVAL_RECORDED else None
            ),
        ),
        recommendation=MaintenanceRecommendation(
            decision=(
                MaintenanceRecommendationDecision.REPAIR
                if approval_status is ApprovalEvidenceStatus.APPROVAL_RECORDED
                else MaintenanceRecommendationDecision.ESCALATE
            ),
            confidence=confidence,
            rationale="Synthetic source-backed maintenance assessment",
            next_steps=("Human review remains required",),
        ),
    )


def prompt_outputs(
    assessment_input: MaintenanceAssessmentInput,
    payload: MaintenanceAssessmentPayload | None = None,
) -> tuple[BaseModel, ...]:
    input_evidence_ids = tuple(
        evidence.evidence_id
        for evidence in (
            *assessment_input.maintenance_history,
            *assessment_input.engineering_constraints,
            *assessment_input.safety_conditions,
        )
    )
    grounding = MaintenanceGroundingOutput(
        evidence_summary="Synthetic validated evidence",
        evidence_references=input_evidence_ids,
        missing_data=(),
        assumptions=(),
        confidence_level=0.82,
    )
    reasoning = MaintenanceReasoningOutput(
        repairability_status=RepairabilityStatus.FEASIBLE,
        findings=("Synthetic repair path",),
        rationale="Synthetic test reasoning",
        technical_risks=(),
        confidence=0.82,
    )
    final = payload or final_payload(assessment_input)
    return grounding, reasoning, final


@pytest.mark.asyncio
async def test_maintenance_agent_runs_bounded_stages_and_returns_shared_envelope() -> None:
    assessment_input = valid_maintenance_input()
    runner = FakePromptRunner(prompt_outputs(assessment_input))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.agent_role is AgentRole.MAINTENANCE
    assert result.status is AgentResultStatus.COMPLETE
    assert runner.stages == [stage.value for stage in MaintenancePromptStage]
    assert runner.instructions == [PROMPT_A_GROUNDING, PROMPT_B_REASONING, PROMPT_C_VALIDATION]
    assert result.confidence == 0.82
    assert result.evidence_references
    assert "airworthiness" not in result.summary.casefold()
    assert result.role_payload["approval_evidence"]["status"] == "approval_recorded"


@pytest.mark.asyncio
async def test_provisional_input_stays_partial_and_confidence_is_reduced() -> None:
    assessment_input = valid_maintenance_input().model_copy(update={"work_order": None})
    runner = FakePromptRunner(prompt_outputs(assessment_input))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.PARTIAL
    assert result.confidence == 0.69
    assert "work_order" in result.role_payload["missing_data"]


@pytest.mark.asyncio
async def test_unapproved_repair_is_escalated_without_agent_approval() -> None:
    assessment_input = valid_maintenance_input()
    payload = final_payload(
        assessment_input,
        approval_status=ApprovalEvidenceStatus.PENDING,
    ).model_copy(update={"repairability_status": RepairabilityStatus.UNCERTAIN})
    runner = FakePromptRunner(prompt_outputs(assessment_input, payload))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.ESCALATION_REQUIRED
    assert result.role_payload["approval_evidence"]["status"] == "pending"
    assert "approved" not in result.summary.casefold()


@pytest.mark.asyncio
async def test_not_feasible_assessment_is_preserved_as_a_domain_result() -> None:
    assessment_input = valid_maintenance_input()
    payload = final_payload(assessment_input).model_copy(
        update={
            "repairability_status": RepairabilityStatus.NOT_FEASIBLE,
            "recommendation": final_payload(assessment_input).recommendation.model_copy(
                update={"decision": MaintenanceRecommendationDecision.DEFER}
            ),
        }
    )
    runner = FakePromptRunner(prompt_outputs(assessment_input, payload))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.COMPLETE
    assert result.role_payload["repairability_status"] == "not_feasible"
    assert result.role_payload["recommendation"]["decision"] == "defer"


@pytest.mark.asyncio
async def test_conflicting_maintenance_evidence_forces_escalation() -> None:
    assessment_input = valid_maintenance_input().model_copy(
        update={
            "maintenance_history": (
                Evidence(
                    evidence_id="maintenance-conflict-001",
                    source="synthetic-conflicting-history",
                    retrieved_at=TIMESTAMP,
                    validity_state=EvidenceValidity.CONFLICTING,
                    claim_reference="conflicting-recurrence-claim",
                    content={"state": "synthetic-conflict"},
                ),
            )
        }
    )
    runner = FakePromptRunner(prompt_outputs(assessment_input))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.ESCALATION_REQUIRED
    assert result.confidence == 0.49
    assert result.role_payload["recommendation"]["decision"] == "escalate"
    assert any("conflicting_evidence" in warning for warning in result.role_payload["warnings"])


def test_maintenance_agent_has_no_approval_or_operational_action_methods() -> None:
    agent = MaintenanceAgent(FakePromptRunner(()))

    assert not hasattr(agent, "approve")
    assert not hasattr(agent, "execute")
    assert not hasattr(agent, "write")


@pytest.mark.asyncio
async def test_unsupported_agent_input_returns_explicit_failed_envelope() -> None:
    payload = valid_maintenance_input().model_dump(mode="python")
    payload["unexpected_instruction"] = "synthetic untrusted field"

    result = await MaintenanceAgent(FakePromptRunner(())).assess(payload)

    assert result.status is AgentResultStatus.FAILED
    assert result.confidence == 0.0
    assert result.role_payload["error"]["category"] == "maintenance_assessment_failed"


@pytest.mark.asyncio
async def test_agent_rejects_prompt_references_to_unavailable_evidence() -> None:
    assessment_input = valid_maintenance_input()
    grounding = MaintenanceGroundingOutput(
        evidence_summary="Synthetic evidence with an unknown reference",
        evidence_references=("evidence-not-in-input",),
        missing_data=(),
        assumptions=(),
        confidence_level=0.8,
    )
    runner = FakePromptRunner((grounding,))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.FAILED
    assert result.role_payload["error"]["case_impact"] == (
        "maintenance input or model output failed at 'evidence_reference_validation'"
    )
    assert len(runner.stages) == 1


@pytest.mark.asyncio
async def test_three_in_ninety_p110_history_is_grounded_and_preferred_part_is_requested() -> None:
    assessment_input = valid_maintenance_input().model_copy(
        update={
            "maintenance_history": tuple(
                Evidence(
                    evidence_id=f"failure-{index}",
                    source="synthetic-maintenance-history",
                    retrieved_at=TIMESTAMP,
                    validity_state=EvidenceValidity.CURRENT,
                    claim_reference=f"failure-claim-{index}",
                    content={
                        "part_number": "P-110",
                        "occurred_at": TIMESTAMP - timedelta(days=day_offset),
                    },
                )
                for index, day_offset in enumerate((89, 45, 0), start=1)
            )
        }
    )
    payload = final_payload(assessment_input).model_copy(
        update={
            "preferred_replacement_part": "P-120",
            "preferred_replacement_evidence_references": ("engineering-001",),
        }
    )
    runner = FakePromptRunner(prompt_outputs(assessment_input, payload))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    recurrence_candidates = runner.payloads[1]["recurring_failure_candidates"]
    assert recurrence_candidates[0]["part_number"] == "P-110"
    assert recurrence_candidates[0]["occurrences"] == 3
    assert result.role_payload["recurring_failure"]["evidence_references"] == [
        "failure-1",
        "failure-2",
        "failure-3",
    ]
    assert result.role_payload["preferred_replacement_part"] == "P-120"
    assert "engineering-001" in result.role_payload["preferred_replacement_evidence_references"]


@pytest.mark.asyncio
async def test_return_to_service_uses_parts_ready_then_ground_time_and_need_by() -> None:
    assessment_input = valid_maintenance_input()
    runner = FakePromptRunner(prompt_outputs(assessment_input))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.role_payload["return_to_service_time"] == "2026-10-21T16:00:00Z"
    assert result.role_payload["meets_need_by_time"] is True


@pytest.mark.asyncio
async def test_missing_parts_ready_time_keeps_return_to_service_unknown() -> None:
    assessment_input = valid_maintenance_input().model_copy(
        update={"parts_ready_at": None, "parts_readiness_evidence_reference": None}
    )
    runner = FakePromptRunner(prompt_outputs(assessment_input))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.PARTIAL
    assert "parts_ready_at" in result.role_payload["missing_data"]
    assert result.role_payload["return_to_service_time"] is None
    assert result.role_payload["meets_need_by_time"] is None


@pytest.mark.asyncio
async def test_missing_need_by_keeps_need_by_comparison_unknown() -> None:
    assessment_input = valid_maintenance_input().model_copy(update={"need_by_time": None})
    runner = FakePromptRunner(prompt_outputs(assessment_input))

    result = await MaintenanceAgent(runner).assess(assessment_input.model_dump(mode="python"))

    assert result.status is AgentResultStatus.PARTIAL
    assert "need_by_time" in result.role_payload["missing_data"]
    assert result.role_payload["return_to_service_time"] == "2026-10-21T16:00:00Z"
    assert result.role_payload["meets_need_by_time"] is None
