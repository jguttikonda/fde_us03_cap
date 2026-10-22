import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aog_recovery.controller.models import (
    CandidateAssessment,
    ConfidenceDisposition,
    ControllerDecisionBrief,
    ControllerIntake,
    ControllerWorkflowStatus,
    RecoveryOptionKind,
    ScoreFactors,
)


def case_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": "req-controller-001",
        "case": {
            "case_id": "AOG-CONTROLLER-001",
            "aircraft_id": "N123AB",
            "event_type": "hydraulic_pump_failure",
            "defect_summary": "Hydraulic pump P-110 failure",
            "location": "MIA",
            "event_at": "2026-10-22T10:00:00Z",
            "created_at": "2026-10-22T10:05:00Z",
            "schema_version": "1.0",
            "trace_context": {
                "trace_id": "trace-controller-001",
                "correlation_id": "corr-controller-001",
            },
        },
        "failed_part_number": "P-110",
        "affected_flight_numbers": ["FX103"],
        "evaluated_at": "2026-10-22T10:10:00Z",
    }


def candidate_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "option_id": "OPT-REPAIR-P120",
        "kind": "repair_alternate",
        "description": "Repair with approved P-120",
        "sourcing_method": "internal_transfer",
        "return_to_service_hours": 6.0,
        "estimated_cost_usd": "1250.00",
        "evidence_references": ["MNT-ETA-001", "ML-QUOTE-001"],
        "assumptions": [],
        "risks": ["Transfer may be delayed"],
        "compliance_eligible": True,
        "exclusion_reasons": [],
        "score_factors": {
            "speed": 80.0,
            "operational_package_impact": 70.0,
            "risk": 75.0,
            "cost": 60.0,
        },
        "aggregate_score": 73.0,
        "trade_off": "Fast recovery depends on the part transfer.",
    }
    payload.update(overrides)
    return payload


def test_controller_intake_accepts_valid_json_and_is_timezone_aware() -> None:
    intake = ControllerIntake.model_validate_json(json.dumps(case_payload()))

    assert intake.case.case_id == "AOG-CONTROLLER-001"
    assert intake.evaluated_at.utcoffset() == UTC.utcoffset(datetime.now(UTC))


def test_controller_intake_rejects_duplicate_flights_and_unknown_fields() -> None:
    duplicate = case_payload()
    duplicate["affected_flight_numbers"] = ["FX103", "FX103"]
    with pytest.raises(ValidationError, match="must be unique"):
        ControllerIntake.model_validate_json(json.dumps(duplicate))

    unknown = case_payload()
    unknown["execute_action"] = True
    with pytest.raises(ValidationError):
        ControllerIntake.model_validate_json(json.dumps(unknown))


def test_excluded_candidate_requires_reason_and_cannot_be_scored() -> None:
    payload = candidate_payload(compliance_eligible=False)

    with pytest.raises(ValidationError, match="excluded candidate requires a reason"):
        CandidateAssessment.model_validate_json(json.dumps(payload))

    payload["exclusion_reasons"] = ["Part traceability is unverified"]
    with pytest.raises(ValidationError, match="excluded candidate must not be scored"):
        CandidateAssessment.model_validate_json(json.dumps(payload))


def test_candidate_score_fields_are_bounded_and_consistent() -> None:
    payload = candidate_payload(
        score_factors={
            "speed": 101.0,
            "operational_package_impact": 70.0,
            "risk": 75.0,
            "cost": 60.0,
        }
    )
    with pytest.raises(ValidationError):
        CandidateAssessment.model_validate_json(json.dumps(payload))

    with pytest.raises(ValidationError, match="supplied together"):
        CandidateAssessment.model_validate_json(json.dumps(candidate_payload(aggregate_score=None)))


def test_decision_brief_requires_human_gate_and_valid_ranked_recommendation() -> None:
    candidate = CandidateAssessment(
        option_id="OPT-REPAIR-P120",
        kind=RecoveryOptionKind.REPAIR_ALTERNATE,
        description="Repair with approved P-120",
        sourcing_method=None,
        return_to_service_hours=6.0,
        estimated_cost_usd=Decimal("1250.00"),
        evidence_references=("MNT-ETA-001",),
        assumptions=(),
        risks=(),
        compliance_eligible=True,
        exclusion_reasons=(),
        score_factors=ScoreFactors(
            speed=80.0,
            operational_package_impact=70.0,
            risk=75.0,
            cost=60.0,
        ),
        aggregate_score=73.0,
        trade_off="Fast recovery depends on transfer.",
    )
    brief = ControllerDecisionBrief(
        schema_version="1.0",
        case_id="AOG-CONTROLLER-001",
        recommendation_version="AOG-CONTROLLER-001-v1",
        status=ControllerWorkflowStatus.COMPLETE,
        summary="P-120 is available through an estimated transfer.",
        relevant_agents=("maintenance", "materials_logistics", "operations"),
        key_findings=("P-120 authorization and traceability are current.",),
        ranked_options=({"rank": 1, "assessment": candidate},),
        excluded_options=(),
        recommended_option_id="OPT-REPAIR-P120",
        recommendation_rationale="Highest eligible score; human review is still required.",
        confidence=0.72,
        confidence_disposition=ConfidenceDisposition.PREFERRED,
        assumptions=(),
        risks=(),
        warnings=(),
        missing_data=(),
        human_approval_required=True,
        next_action="Human maintenance and operations review is required.",
    )

    assert brief.human_approval_required is True

    with pytest.raises(ValidationError):
        ControllerDecisionBrief.model_validate(
            {**brief.model_dump(), "human_approval_required": False}
        )
