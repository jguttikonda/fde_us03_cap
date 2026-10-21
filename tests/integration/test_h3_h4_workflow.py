from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aog_recovery.contracts.case import AogCase, TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolResultStatus
from aog_recovery.coordination.models import DegradationStatus, ExchangeStatus
from aog_recovery.coordination.recording import (
    ExchangeDirection,
    ExchangeRecordingStatus,
    InMemoryCaseContextRecorder,
)
from aog_recovery.coordination.workflow import (
    build_h3_request,
    coordinate_h3_h4,
)
from aog_recovery.maintenance.models import (
    ApprovalEvidenceStatus,
    EngineeringApprovalEvidence,
    MaintenanceAssessmentPayload,
    MaintenanceRecommendation,
    MaintenanceRecommendationDecision,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RecurringFailureSummary,
    RepairabilityStatus,
    RootCauseEvidence,
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


def case() -> AogCase:
    return AogCase(
        case_id="case-peer-001",
        aircraft_id="TEST-AIRCRAFT-001",
        event_type="synthetic_aog",
        defect_summary="Synthetic hydraulic defect",
        location="TEST-STATION-A",
        event_at=TIMESTAMP,
        created_at=TIMESTAMP,
        schema_version="1.0",
        trace_context=TraceContext(trace_id="trace-peer-001", correlation_id="corr-peer-001"),
    )


def maintenance_payload() -> MaintenanceAssessmentPayload:
    return MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.UNCERTAIN,
        root_cause=RootCauseEvidence(
            category="synthetic_hydraulic_failure",
            confidence=0.75,
            evidence_references=("maintenance-history-P110",),
        ),
        recurring_failure=RecurringFailureSummary(
            part_number="P-110",
            occurrences=3,
            window_days=90,
            evidence_references=("maintenance-history-P110",),
        ),
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("engineering-preference-P120",),
        required_actions=("synthetic_inspection",),
        estimated_ground_time_hours=4.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("125.00"),
        need_by_time=TIMESTAMP + timedelta(hours=5),
        parts_ready_at=None,
        return_to_service_time=None,
        meets_need_by_time=None,
        eta_confidence=0.65,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.MEDIUM,
            parts_dependency_risk=MaintenanceRiskLevel.MEDIUM,
            repair_complexity_risk=MaintenanceRiskLevel.UNKNOWN,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.UNKNOWN,
            approver_role=None,
            source_reference=None,
            recorded_at=None,
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.UNCERTAIN,
            confidence=0.65,
            rationale="Synthetic advisory assessment",
            next_steps=("Human technical review remains required",),
        ),
    )


def h3_request(
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
) -> object:
    source_evidence = (
        Evidence(
            evidence_id="maintenance-history-P110",
            source="synthetic-maintenance-history",
            retrieved_at=TIMESTAMP,
            validity_state=validity,
            claim_reference="claim-maintenance-history-P110",
            content={"part_number": "P-110", "occurrences": 3},
        ),
        Evidence(
            evidence_id="engineering-preference-P120",
            source="synthetic-engineering-record",
            retrieved_at=TIMESTAMP,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference="claim-engineering-preference-P120",
            content={"preferred_part": "P-120"},
        ),
    )
    return build_h3_request(
        case(),
        maintenance_payload(),
        failed_part_number="P-110",
        exchange_id="exchange-peer-001",
        request_id="request-peer-001",
        sent_at=TIMESTAMP,
        source_evidence=source_evidence,
    )


def materials_payload(
    *,
    include_preferred: bool = True,
    preferred_validity: EvidenceValidity = EvidenceValidity.CURRENT,
) -> MaterialsLogisticsAssessmentPayload:
    records = [
        PartAvailabilityRecord(
            part_number="P-110",
            role=PartRole.FAILED_PART,
            required_quantity=1,
            available_quantity=0,
            minimum_stock_threshold=0,
            location="TEST-STATION-A",
            source="synthetic-inventory",
            retrieved_at=TIMESTAMP,
            validity_state=EvidenceValidity.CURRENT,
            claim_reference="inventory-claim-P110",
        )
    ]
    eligibility = []
    sourcing_options = []
    if include_preferred:
        records.append(
            PartAvailabilityRecord(
                part_number="P-120",
                role=PartRole.PREFERRED_REPLACEMENT,
                required_quantity=1,
                available_quantity=4,
                minimum_stock_threshold=1,
                location="TEST-STATION-A",
                source="synthetic-inventory",
                retrieved_at=TIMESTAMP,
                validity_state=preferred_validity,
                claim_reference="inventory-claim-P120",
            )
        )
        eligibility.append(
            PartEligibilityEvidence(
                part_number="P-120",
                compatibility=CompatibilityStatus.COMPATIBLE,
                authorization=AuthorizationStatus.AUTHORIZED,
                traceability=TraceabilityStatus.VERIFIED,
                checked_by_role="materials_inventory_specialist",
                evidence_references=("eligibility-P120",),
            )
        )
        sourcing_options.append(
            SourcingOption(
                part_number="P-120",
                source="synthetic-stock-location",
                source_location="TEST-STATION-A",
                method=SourcingMethod.INTERNAL_TRANSFER,
                shipping_provider=ShippingProvider.FEDEX_NETWORK,
                shipping_service="priority_freight",
                transfer_required=False,
                lead_time_hours=1.0,
                eta_at=TIMESTAMP + timedelta(hours=1),
                estimated_cost_usd=Decimal("20.00"),
                quote_unavailable_reason=None,
                evidence_references=("quote-P120",),
            )
        )
    return MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.AVAILABLE
        if include_preferred
        else AvailabilityStatus.UNCERTAIN,
        part_availability=tuple(records),
        part_eligibility=tuple(eligibility),
        sourcing_options=tuple(sourcing_options),
        confidence=0.8,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
    )


def current_evidence_summary() -> MaterialsEvidenceSummary:
    return MaterialsEvidenceSummary(
        status=ToolResultStatus.SUCCESS,
        confidence=0.8,
        evidence_references=("inventory-evidence-P110", "inventory-evidence-P120"),
        warnings=(),
        errors=(),
    )


def coordinate(
    request: object,
    materials: MaterialsLogisticsAssessmentPayload,
    summary: MaterialsEvidenceSummary,
    recorder: InMemoryCaseContextRecorder | None = None,
):
    return coordinate_h3_h4(
        request,
        materials,
        summary,
        response_id="response-peer-001",
        responded_at=TIMESTAMP + timedelta(minutes=1),
        recorder=recorder or InMemoryCaseContextRecorder(),
    )


def test_p110_p120_three_in_ninety_exchange_preserves_both_part_results() -> None:
    peer_exchange = coordinate(h3_request(), materials_payload(), current_evidence_summary())
    request = peer_exchange.exchange.request
    response = peer_exchange.exchange.response

    assert request.recurring_failure_count == 3
    assert request.recurring_failure_window_days == 90
    assert request.preferred_part_number == "P-120"
    assert response.status is ExchangeStatus.COMPLETE
    assert (
        response.part_comparison.failed_part_assessments[0].availability_status
        is AvailabilityStatus.UNAVAILABLE
    )
    assert (
        response.part_comparison.preferred_part_assessments[0].availability_status
        is AvailabilityStatus.AVAILABLE
    )
    assert response.part_comparison.preferred_part_assessments[0].eligible is True
    assert peer_exchange.recording.status is ExchangeRecordingStatus.COMPLETE
    assert [record.direction for record in peer_exchange.recording.records] == [
        ExchangeDirection.REQUEST,
        ExchangeDirection.RESPONSE,
    ]


def test_missing_preferred_part_is_returned_as_partial_not_omitted() -> None:
    peer_exchange = coordinate(
        h3_request(),
        materials_payload(include_preferred=False),
        current_evidence_summary(),
    )
    response = peer_exchange.exchange.response

    assert response.status is ExchangeStatus.PARTIAL
    assert response.degradation_status is DegradationStatus.MISSING
    assert response.part_comparison.preferred_part_assessments == ()
    assert "P-120" in response.missing_data


def test_stale_source_confidence_and_provenance_reach_h4_and_recorder() -> None:
    warning = EvidenceWarning(
        warning_id="stale-inventory-warning",
        claim_reference="claim-inventory-P120",
        code="STALE_EVIDENCE",
        message="inventory evidence is stale",
        source_reference="synthetic-inventory",
    )
    stale_source = MaterialsEvidenceSummary(
        status=ToolResultStatus.PARTIAL,
        confidence=0.7,
        evidence_references=("inventory-evidence-P120",),
        warnings=(warning,),
        errors=(),
    )
    recorder = InMemoryCaseContextRecorder()

    peer_exchange = coordinate(h3_request(), materials_payload(), stale_source, recorder)
    response = peer_exchange.exchange.response
    recorded_response = recorder.records_for("case-peer-001", "exchange-peer-001")[1]

    assert response.status is ExchangeStatus.PARTIAL
    assert response.degradation_status is DegradationStatus.STALE
    assert response.confidence == 0.7
    assert "inventory-evidence-P120" in response.evidence_references
    assert response.warnings == (warning,)
    assert recorded_response.direction is ExchangeDirection.RESPONSE
    assert recorded_response.message.conflicts == ()


def test_conflicting_inventory_is_preserved_for_controller_case_context() -> None:
    recorder = InMemoryCaseContextRecorder()
    peer_exchange = coordinate(
        h3_request(),
        materials_payload(preferred_validity=EvidenceValidity.CONFLICTING),
        current_evidence_summary(),
        recorder,
    )
    response = peer_exchange.exchange.response
    recorded_response = recorder.records_for("case-peer-001", "exchange-peer-001")[1]

    assert response.status is ExchangeStatus.CONFLICTED
    assert response.degradation_status is DegradationStatus.CONFLICTING
    assert response.conflicts == ("P-120: inventory_evidence_conflicting",)
    assert recorded_response.message.conflicts == response.conflicts
    assert peer_exchange.recording.status is ExchangeRecordingStatus.COMPLETE


def test_stale_maintenance_evidence_marks_h3_and_carries_its_reference() -> None:
    request = h3_request(EvidenceValidity.STALE)

    assert request.status is ExchangeStatus.PARTIAL
    assert request.degradation_status is DegradationStatus.STALE
    assert "maintenance-history-P110" in request.maintenance_evidence_references
    assert request.warnings[0].code == "STALE_EVIDENCE"
