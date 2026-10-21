import json
from datetime import UTC, datetime

from aog_recovery.adapters.local import MockResponseMode
from aog_recovery.contracts.agent import AgentResultStatus, AgentRole
from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Unknown
from aog_recovery.contracts.governance import (
    HumanDecisionRecord,
    HumanDecisionType,
    ReviewerRole,
)
from aog_recovery.contracts.tool import ToolName, ToolResultStatus
from aog_recovery.observability.structured import LOGGER
from aog_recovery.validation.boundaries import validate_agent_result, validate_case
from aog_recovery.validation.confidence import (
    ConfidenceDisposition,
    assess_confidence,
)
from aog_recovery.validation.human_gate import HumanGateStatus, assess_human_gate

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def _decision(role: ReviewerRole) -> HumanDecisionRecord:
    return HumanDecisionRecord(
        schema_version="1.0",
        decision_id=f"decision-{role.value}",
        case_id="case-synthetic-001",
        decision=HumanDecisionType.APPROVE,
        selected_action="synthetic-repair",
        selected_option_id="option-synthetic-001",
        reviewer_id=f"reviewer-{role.value}",
        reviewer_role=role,
        decided_at=TIMESTAMP,
        rationale="Synthetic integration approval",
        recommendation_version="recommendation-synthetic-v1",
    )


def test_foundation_preserves_degradation_and_requires_human_approval(
    caplog,
    valid_case: AogCase,
    agent_result_payload: dict[str, object],
    current_evidence,
    stale_evidence,
    partial_evidence,
    conflicting_evidence,
    trace_context: TraceContext,
    tool_request_factory,
    local_adapter_factory,
) -> None:
    case_report = validate_case(valid_case.model_dump(mode="python"))
    result_report = validate_agent_result(
        agent_result_payload,
        available_evidence_ids={current_evidence.evidence_id},
    )

    assert case_report.is_valid
    assert result_report.is_valid
    assert agent_result_payload["status"] is AgentResultStatus.PARTIAL
    assert stale_evidence.validity_state.value == "stale"
    assert partial_evidence.validity_state.value == "partial"

    request = tool_request_factory(ToolName.MAINTENANCE_RECORDS)
    degraded_results = {
        mode: local_adapter_factory(mode).read(request, AgentRole.MAINTENANCE)
        for mode in (
            MockResponseMode.UNAVAILABLE,
            MockResponseMode.MALFORMED,
            MockResponseMode.STALE,
            MockResponseMode.PARTIAL,
            MockResponseMode.CONFLICTING,
        )
    }
    for mode in (MockResponseMode.UNAVAILABLE, MockResponseMode.MALFORMED):
        assert degraded_results[mode].status is ToolResultStatus.FAILED
        assert degraded_results[mode].data is None
        assert degraded_results[mode].error is not None
    for mode in (MockResponseMode.STALE, MockResponseMode.PARTIAL, MockResponseMode.CONFLICTING):
        assert degraded_results[mode].status is ToolResultStatus.PARTIAL
        assert degraded_results[mode].warnings

    _, _, conflict = conflicting_evidence
    unknown = Unknown(
        claim_reference="claim-synthetic-unknown",
        description="Synthetic evidence not supplied",
        required_evidence=("synthetic-required-record",),
    )
    low_confidence = assess_confidence(0.49, conflicts=(), unknowns=(unknown,))
    conflict_override = assess_confidence(0.95, conflicts=(conflict,), unknowns=(unknown,))
    assert low_confidence.disposition is ConfidenceDisposition.ESCALATION_REQUIRED
    assert conflict_override.disposition is ConfidenceDisposition.ESCALATION_REQUIRED
    assert conflict_override.unknown_claim_references == (unknown.claim_reference,)

    with caplog.at_level("INFO", logger=LOGGER.name):
        logged_result = local_adapter_factory(MockResponseMode.PARTIAL).read(
            request, AgentRole.MAINTENANCE
        )
    event = json.loads(caplog.records[-1].message)
    assert event["case_id"] == valid_case.case_id
    assert event["request_id"] == request.request_id
    assert event["trace_context"]["trace_id"] == trace_context.trace_id
    assert event["status"] == logged_result.status.value

    gate = assess_human_gate(
        decisions=(
            _decision(ReviewerRole.OPS_LEAD),
            _decision(ReviewerRole.MAINTENANCE_AIRWORTHINESS),
        ),
        case_id=valid_case.case_id,
        recommendation_version="recommendation-synthetic-v1",
        requires_repair_or_part_approval=True,
    )
    pending_gate = assess_human_gate(
        decisions=(),
        case_id=valid_case.case_id,
        recommendation_version="recommendation-synthetic-v1",
        requires_repair_or_part_approval=True,
    )

    assert gate.status is HumanGateStatus.APPROVED
    assert pending_gate.status is HumanGateStatus.PENDING
