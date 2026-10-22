from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.case import TraceContext
from aog_recovery.operations.contracts import (
    AssessmentStatus,
    CostEstimate,
    CostLineItem,
    EvidenceState,
    ImpactLevel,
    OperationsAssessment,
    OperationsEvidence,
    OperationsRecommendation,
    OperationsRequest,
    PackageRedistribution,
    PackageServiceCount,
    RecoveryCandidate,
    RecoveryOptionKind,
    TailPackageAllocation,
)

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
TRACE = TraceContext(trace_id="trace-ops-001", correlation_id="corr-ops-001")
REQUIREMENT_TO_TEST = {
    "Validate and preserve operational evidence": (
        "test_evidence_requires_provenance_and_timezone",
        "test_assessment_keeps_evidence_and_assumptions_separate",
    ),
    "Return a structured Operations assessment": (
        "test_valid_request_and_assessment_contracts",
        "test_unavailable_cost_is_not_zero",
    ),
}


def test_requirement_to_test_map_covers_contract_requirements() -> None:
    assert all(test_names for test_names in REQUIREMENT_TO_TEST.values())


def test_evidence_requires_provenance_and_timezone() -> None:
    evidence = OperationsEvidence(
        evidence_id="ev-flight-001",
        source="mock-flight-ops",
        observed_at=NOW,
        state=EvidenceState.CURRENT,
        subject="flight FX401 schedule",
        value={"departure": NOW.isoformat()},
    )

    assert evidence.source == "mock-flight-ops"
    assert evidence.observed_at == NOW
    assert evidence.state is EvidenceState.CURRENT

    with pytest.raises(ValidationError, match="timezone"):
        OperationsEvidence(
            evidence_id="ev-invalid",
            source="mock-flight-ops",
            observed_at=datetime(2026, 10, 21, 12, 0),
            state=EvidenceState.CURRENT,
            subject="flight schedule",
            value={"departure": "unknown"},
        )

    with pytest.raises(ValidationError, match="requires a value"):
        OperationsEvidence(
            evidence_id="ev-empty",
            source="mock-flight-ops",
            observed_at=NOW,
            state=EvidenceState.CURRENT,
            subject="flight schedule",
            value=None,
        )


def test_valid_request_and_assessment_contracts() -> None:
    candidate = RecoveryCandidate(
        option_id="swap-fx207",
        kind=RecoveryOptionKind.SWAP,
        description="Evaluate spare aircraft FX207",
        substitute_tail_id="FX207",
        evidence_references=("ev-fleet-001",),
    )
    request = OperationsRequest(
        schema_version="1.0",
        case_id="case-ops-001",
        trace_context=TRACE,
        affected_flight_ids=("FX401",),
        candidates=(candidate,),
        evidence_references=("ev-fleet-001",),
    )
    assessment = OperationsAssessment(
        schema_version="1.0",
        case_id=request.case_id,
        trace_context=TRACE,
        status=AssessmentStatus.COMPLETE,
        confidence=0.75,
        impact_level=ImpactLevel.LOW,
        option_assessments=(),
        evidence=(),
        assumptions=(),
        missing_evidence=(),
        conflicts=(),
        errors=(),
        recommendation=OperationsRecommendation(
            preferred_option_id=candidate.option_id,
            status="preferred",
            confidence=0.75,
            rationale="Mock fixture supports the candidate.",
            next_steps=("Request authorized human review.",),
        ),
        summary="Mock Operations assessment.",
        tradeoff_notes=(),
    )

    assert request.candidates[0].substitute_tail_id == "FX207"
    assert assessment.recommendation.human_approval_required is True
    assert assessment.final_report is None
    assert assessment.system_ranked_option_ids is None


@pytest.mark.parametrize(
    ("kind", "fields", "message"),
    [
        (RecoveryOptionKind.REPAIR, {}, "require repair_eta"),
        (
            RecoveryOptionKind.SWAP,
            {"substitute_tail_id": "FX207", "repair_eta": NOW},
            "repair_eta is only valid",
        ),
        (RecoveryOptionKind.DELAY, {"delay_minutes": 0}, "greater than 0"),
    ],
)
def test_candidate_rejects_missing_or_inapplicable_fields(
    kind: RecoveryOptionKind,
    fields: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        RecoveryCandidate(
            option_id="candidate-invalid",
            kind=kind,
            description="Invalid mock candidate",
            **fields,
        )


def test_request_rejects_duplicate_options_and_unknown_fields() -> None:
    candidate = RecoveryCandidate(
        option_id="swap-fx207",
        kind=RecoveryOptionKind.SWAP,
        description="Evaluate spare aircraft FX207",
        substitute_tail_id="FX207",
    )
    payload = {
        "schema_version": "1.0",
        "case_id": "case-ops-001",
        "trace_context": TRACE,
        "affected_flight_ids": ("FX401",),
        "candidates": (candidate, candidate),
        "unexpected": "must be rejected",
    }

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        OperationsRequest.model_validate(payload)

    del payload["unexpected"]
    with pytest.raises(ValidationError, match="option_id values must be unique"):
        OperationsRequest.model_validate(payload)


def test_package_allocation_cannot_exceed_capacity_or_lose_packages() -> None:
    with pytest.raises(ValidationError, match="exceeds tail capacity"):
        TailPackageAllocation(
            tail_id="FX207",
            capacity=900,
            package_count=901,
            packages_by_service_level=(
                PackageServiceCount(service_level="priority", package_count=901),
            ),
        )

    with pytest.raises(ValidationError, match="must equal total_package_count"):
        PackageRedistribution(
            total_package_count=10,
            protected_by_service_level=(
                PackageServiceCount(service_level="priority", package_count=8),
            ),
            unprotected_by_service_level=(
                PackageServiceCount(service_level="standard", package_count=1),
            ),
            allocations=(
                TailPackageAllocation(
                    tail_id="FX207",
                    capacity=8,
                    package_count=8,
                    packages_by_service_level=(
                        PackageServiceCount(service_level="priority", package_count=8),
                    ),
                ),
            ),
        )


def test_unavailable_cost_is_not_zero() -> None:
    estimate = CostEstimate(
        total=None,
        currency="USD",
        line_items=(),
        unavailable_reason="Mock exposure rate is not configured.",
        missing_evidence=("package-exposure-rate",),
    )

    assert estimate.total is None
    assert estimate.unavailable_reason is not None
    with pytest.raises(ValidationError, match="unavailable_reason"):
        CostEstimate(total=None, currency="USD", line_items=())

    with pytest.raises(ValidationError, match="sum of its line items"):
        CostEstimate(
            total=Decimal("10.00"),
            currency="USD",
            line_items=(
                CostLineItem(description="Mock swap cost", amount=Decimal("9.00"), currency="USD"),
            ),
        )


def test_assessment_keeps_evidence_and_assumptions_separate() -> None:
    evidence = OperationsEvidence(
        evidence_id="ev-cutoff-001",
        source="mock-package-ops",
        observed_at=NOW,
        state=EvidenceState.CURRENT,
        subject="FX401 package cut-off",
        value={"cutoff": "2026-10-21T15:00:00Z"},
    )
    assessment = OperationsAssessment(
        schema_version="1.0",
        case_id="case-ops-001",
        trace_context=TRACE,
        status=AssessmentStatus.PARTIAL,
        confidence=0.55,
        impact_level=ImpactLevel.MEDIUM,
        option_assessments=(),
        evidence=(evidence,),
        assumptions=(),
        missing_evidence=("alternate-tail-sort-window",),
        conflicts=(),
        errors=(),
        recommendation=OperationsRecommendation(
            preferred_option_id=None,
            status="provisional",
            confidence=0.55,
            rationale="The alternate-tail sort window is missing.",
            next_steps=("Confirm the sort window.",),
        ),
        summary="Partial mock assessment.",
        tradeoff_notes=(),
    )

    assert assessment.evidence[0].evidence_id == "ev-cutoff-001"
    assert assessment.assumptions == ()
    assert assessment.missing_evidence == ("alternate-tail-sort-window",)
