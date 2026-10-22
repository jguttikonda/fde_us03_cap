from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import BaseModel

from aog_recovery.contracts.agent import (
    AgentResult,
    AgentResultStatus,
    AgentRole,
    StructuredError,
)
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.materials_logistics.agent import (
    GoogleAdkMaterialsPromptRunner,
    MaterialsFinalOutput,
    MaterialsGroundingOutput,
    MaterialsLogisticsAgent,
    MaterialsPromptStage,
    MaterialsReasoningOutput,
)
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsEvidenceSummary,
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartRole,
    ShippingProvider,
    SourcingMethod,
    SourcingOption,
    TraceabilityStatus,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


class FakeMaterialsPromptRunner:
    def __init__(self, outputs: tuple[BaseModel | Mapping[str, object], ...]) -> None:
        self.outputs = list(outputs)
        self.stages: list[MaterialsPromptStage] = []
        self.payloads: list[Mapping[str, object]] = []

    async def run_stage(
        self,
        stage: MaterialsPromptStage,
        payload: Mapping[str, object],
    ) -> BaseModel | Mapping[str, object]:
        self.stages.append(stage)
        self.payloads.append(payload)
        return self.outputs.pop(0)


class FakeSharedPromptRunner:
    def __init__(self, outputs: tuple[BaseModel, ...]) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, object]] = []

    async def run_prompt(
        self,
        *,
        agent_name: str,
        stage_name: str,
        instruction: str,
        inputs: dict[str, object],
        output_model: type[BaseModel],
    ) -> BaseModel:
        self.calls.append(
            {
                "agent_name": agent_name,
                "stage_name": stage_name,
                "instruction": instruction,
                "inputs": inputs,
                "output_model": output_model,
            }
        )
        return self.outputs.pop(0)


def case() -> AogCase:
    return AogCase(
        case_id="case-materials-001",
        aircraft_id="TEST-AIRCRAFT-001",
        event_type="synthetic_aog",
        defect_summary="Synthetic hydraulic failure",
        location="TEST-STATION-A",
        event_at=TIMESTAMP,
        created_at=TIMESTAMP,
        schema_version="1.0",
        trace_context=TraceContext(trace_id="trace-materials-001", correlation_id="corr-001"),
    )


def assessment() -> MaterialsLogisticsAssessmentPayload:
    return MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.AVAILABLE,
        part_availability=(
            PartAvailabilityRecord(
                part_number="P-120",
                role=PartRole.PREFERRED_REPLACEMENT,
                required_quantity=1,
                available_quantity=4,
                minimum_stock_threshold=1,
                location="TEST-STATION-A",
                source="synthetic-inventory",
                retrieved_at=TIMESTAMP,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="inventory-claim-P120",
            ),
        ),
        part_eligibility=(
            PartEligibilityEvidence(
                part_number="P-120",
                compatibility=CompatibilityStatus.COMPATIBLE,
                authorization=AuthorizationStatus.AUTHORIZED,
                traceability=TraceabilityStatus.VERIFIED,
                checked_by_role="materials_inventory_specialist",
                evidence_references=("eligibility-P120",),
            ),
        ),
        sourcing_options=(
            SourcingOption(
                part_number="P-120",
                source="synthetic-stock-location",
                source_location="TEST-STATION-A",
                method=SourcingMethod.INTERNAL_TRANSFER,
                shipping_provider=ShippingProvider.FEDEX_NETWORK,
                shipping_service="priority_freight",
                transfer_required=False,
                lead_time_hours=2.0,
                eta_at=TIMESTAMP,
                estimated_cost_usd=Decimal("20.00"),
                quote_unavailable_reason=None,
                evidence_references=("quote-P120",),
                assumptions=("synthetic quote",),
            ),
        ),
        confidence=0.82,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
    )


def evidence_summary(
    *,
    status: ToolResultStatus = ToolResultStatus.SUCCESS,
    confidence: float = 0.82,
    warnings: tuple[EvidenceWarning, ...] = (),
    errors: tuple[StructuredError, ...] = (),
) -> MaterialsEvidenceSummary:
    return MaterialsEvidenceSummary(
        status=status,
        confidence=confidence,
        evidence_references=(
            "inventory-claim-P120",
            "eligibility-P120",
            "quote-P120",
        ),
        warnings=warnings,
        errors=errors,
    )


def outputs(
    *,
    final_references: tuple[str, ...] = ("inventory-claim-P120", "quote-P120"),
) -> tuple[BaseModel, ...]:
    return (
        MaterialsGroundingOutput(
            evidence_summary="Current synthetic P-120 inventory and authorization",
            evidence_references=("inventory-claim-P120", "eligibility-P120"),
            missing_data=(),
            assumptions=(),
            confidence_level=0.82,
        ),
        MaterialsReasoningOutput(
            summary="P-120 is practically available at the target station",
            risk_factors=("synthetic supply risk",),
            assumptions=(),
            missing_data=(),
            confidence=0.82,
        ),
        MaterialsFinalOutput(
            summary="P-120 is available for human evaluation",
            evidence_references=final_references,
            risk_factors=("synthetic supply risk",),
            assumptions=(),
            missing_data=(),
            confidence=0.82,
        ),
    )


def agent_result_payload(
    source_summary: MaterialsEvidenceSummary | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "case": case().model_dump(mode="python"),
        "assessment": assessment().model_dump(mode="python"),
        "evidence_summary": (source_summary or evidence_summary()).model_dump(mode="python"),
    }


def assessment_result_payload(result: object) -> dict[str, object]:
    agent_result = cast(AgentResult, result)
    return cast(dict[str, object], agent_result.role_payload["assessment"])


def evidence_summary_result_payload(result: object) -> dict[str, object]:
    agent_result = cast(AgentResult, result)
    return cast(dict[str, object], agent_result.role_payload["evidence_summary"])


def error_result_payload(result: object) -> dict[str, object]:
    agent_result = cast(AgentResult, result)
    return cast(dict[str, object], agent_result.role_payload["error"])


@pytest.mark.asyncio
async def test_google_adk_adapter_maps_each_stage_to_its_typed_output() -> None:
    shared_runner = FakeSharedPromptRunner(outputs())
    adk_runner = GoogleAdkMaterialsPromptRunner(shared_runner)

    for stage in MaterialsPromptStage:
        await adk_runner.run_stage(stage, {"case_id": "case-materials-001"})

    assert [call["agent_name"] for call in shared_runner.calls] == [
        "materials_logistics_agent",
        "materials_logistics_agent",
        "materials_logistics_agent",
    ]
    assert [call["stage_name"] for call in shared_runner.calls] == [
        stage.value for stage in MaterialsPromptStage
    ]
    assert [call["output_model"] for call in shared_runner.calls] == [
        MaterialsGroundingOutput,
        MaterialsReasoningOutput,
        MaterialsFinalOutput,
    ]
    assert all(call["instruction"] for call in shared_runner.calls)


@pytest.mark.asyncio
async def test_agent_runs_bounded_stages_and_preserves_deterministic_fields() -> None:
    source_assessment = assessment()
    runner = FakeMaterialsPromptRunner(outputs())

    result = await MaterialsLogisticsAgent(runner).assess(agent_result_payload())

    final_assessment = assessment_result_payload(result)
    assert result.agent_role is AgentRole.MATERIALS_LOGISTICS
    assert result.status is AgentResultStatus.COMPLETE
    assert result.confidence == 0.82
    assert runner.stages == list(MaterialsPromptStage)
    assert (
        final_assessment["part_availability"]
        == source_assessment.model_dump(mode="json")["part_availability"]
    )
    assert (
        final_assessment["part_eligibility"]
        == source_assessment.model_dump(mode="json")["part_eligibility"]
    )
    assert (
        final_assessment["sourcing_options"]
        == source_assessment.model_dump(mode="json")["sourcing_options"]
    )
    assert "quote-P120" in result.evidence_references


@pytest.mark.asyncio
async def test_partial_source_warnings_and_lower_confidence_reach_agent_result() -> None:
    warning = EvidenceWarning(
        warning_id="stale-P120",
        claim_reference="claim-P120",
        code="STALE_EVIDENCE",
        message="inventory data is stale",
        source_reference="synthetic-inventory",
    )
    summary = evidence_summary(
        status=ToolResultStatus.PARTIAL,
        confidence=0.69,
        warnings=(warning,),
    )
    runner = FakeMaterialsPromptRunner(outputs())

    result = await MaterialsLogisticsAgent(runner).assess(agent_result_payload(summary))

    assert result.status is AgentResultStatus.PARTIAL
    assert result.confidence == 0.69
    summary_payload = evidence_summary_result_payload(result)
    warnings = cast(list[dict[str, object]], summary_payload["warnings"])
    assert warnings[0]["code"] == "STALE_EVIDENCE"


@pytest.mark.asyncio
async def test_missing_material_data_survives_agent_normalization() -> None:
    source_assessment = assessment().model_copy(update={"missing_data": ("supplier lead time",)})
    source_input = {
        "schema_version": "1.0",
        "case": case().model_dump(mode="python"),
        "assessment": source_assessment.model_dump(mode="python"),
        "evidence_summary": evidence_summary().model_dump(mode="python"),
    }

    result = await MaterialsLogisticsAgent(FakeMaterialsPromptRunner(outputs())).assess(
        source_input
    )

    assert result.status is AgentResultStatus.PARTIAL
    assert "supplier lead time" in assessment_result_payload(result)["missing_data"]


@pytest.mark.asyncio
async def test_conflicting_source_evidence_escalates_without_losing_conflict() -> None:
    warning = EvidenceWarning(
        warning_id="conflict-P120",
        claim_reference="claim-P120",
        code="CONFLICTING_DATA",
        message="inventory sources disagree",
        source_reference="synthetic-inventory",
    )
    summary = evidence_summary(
        status=ToolResultStatus.PARTIAL,
        confidence=0.49,
        warnings=(warning,),
    )
    runner = FakeMaterialsPromptRunner(outputs())

    result = await MaterialsLogisticsAgent(runner).assess(agent_result_payload(summary))

    assert result.status is AgentResultStatus.ESCALATION_REQUIRED
    assert result.confidence == 0.49
    summary_payload = evidence_summary_result_payload(result)
    warnings = cast(list[dict[str, object]], summary_payload["warnings"])
    assert warnings[0]["code"] == "CONFLICTING_DATA"


@pytest.mark.asyncio
async def test_all_source_failures_return_structured_failure_without_model_calls() -> None:
    source_error = StructuredError(
        schema_version="1.0",
        category="source_unavailable",
        component="synthetic-inventory",
        message="inventory source unavailable",
        retryable=True,
        case_impact="part availability is unknown",
    )
    summary = evidence_summary(
        status=ToolResultStatus.FAILED,
        confidence=0.0,
        errors=(source_error,),
    )
    runner = FakeMaterialsPromptRunner(())

    result = await MaterialsLogisticsAgent(runner).assess(agent_result_payload(summary))

    assert result.status is AgentResultStatus.FAILED
    assert result.confidence == 0.0
    assert error_result_payload(result)["category"] == "materials_sources_unavailable"
    assert runner.stages == []


@pytest.mark.asyncio
async def test_invalid_schema_and_malformed_prompt_output_fail_explicitly() -> None:
    payload = agent_result_payload()
    payload["schema_version"] = "2.0"
    invalid = await MaterialsLogisticsAgent(FakeMaterialsPromptRunner(())).assess(payload)
    malformed = await MaterialsLogisticsAgent(
        FakeMaterialsPromptRunner(({"unexpected": "field"},))
    ).assess(agent_result_payload())

    assert invalid.status is AgentResultStatus.FAILED
    assert invalid.confidence == 0.0
    assert malformed.status is AgentResultStatus.FAILED
    assert error_result_payload(malformed)["category"] == "materials_prompt_failed"


@pytest.mark.asyncio
async def test_blank_final_summary_is_rejected_by_output_contract() -> None:
    normal_outputs = outputs()
    stage_outputs: tuple[BaseModel | Mapping[str, object], ...] = (
        *normal_outputs[:2],
        {**normal_outputs[-1].model_dump(mode="python"), "summary": ""},
    )

    result = await MaterialsLogisticsAgent(FakeMaterialsPromptRunner(tuple(stage_outputs))).assess(
        agent_result_payload()
    )

    assert result.status is AgentResultStatus.FAILED
    assert error_result_payload(result)["category"] == "materials_prompt_failed"


@pytest.mark.asyncio
async def test_unknown_grounding_or_final_evidence_reference_is_rejected() -> None:
    invalid_grounding = (
        MaterialsGroundingOutput(
            evidence_summary="unsupported evidence",
            evidence_references=("unknown-evidence",),
            missing_data=(),
            assumptions=(),
            confidence_level=0.8,
        ),
    )
    grounding_result = await MaterialsLogisticsAgent(
        FakeMaterialsPromptRunner(invalid_grounding)
    ).assess(agent_result_payload())

    invalid_final = await MaterialsLogisticsAgent(
        FakeMaterialsPromptRunner(outputs(final_references=("unknown-evidence",)))
    ).assess(agent_result_payload())

    assert grounding_result.status is AgentResultStatus.FAILED
    assert invalid_final.status is AgentResultStatus.FAILED
    assert error_result_payload(grounding_result)["category"] == (
        "materials_evidence_reference_invalid"
    )
    assert error_result_payload(invalid_final)["category"] == (
        "materials_evidence_reference_invalid"
    )


def test_agent_exposes_no_ranking_approval_or_sourcing_action_methods() -> None:
    agent = MaterialsLogisticsAgent(FakeMaterialsPromptRunner(()))

    assert not hasattr(agent, "rank")
    assert not hasattr(agent, "approve")
    assert not hasattr(agent, "execute")
    assert not hasattr(agent, "purchase")
    assert not hasattr(agent, "reserve")
    assert not hasattr(agent, "transfer")
    assert not hasattr(agent, "ship")
