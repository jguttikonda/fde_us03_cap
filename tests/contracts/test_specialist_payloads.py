from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.evidence import EvidenceValidity
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


def maintenance_payload() -> MaintenanceAssessmentPayload:
    return MaintenanceAssessmentPayload(
        schema_version="1.0",
        repairability_status=RepairabilityStatus.FEASIBLE,
        root_cause=RootCauseEvidence(
            category="synthetic_hydraulic_failure",
            confidence=0.8,
            evidence_references=("maintenance-record-synthetic-001",),
        ),
        recurring_failure=RecurringFailureSummary(
            part_number="P-110",
            occurrences=3,
            window_days=90,
            evidence_references=("history-synthetic-001",),
        ),
        preferred_replacement_part="P-120",
        preferred_replacement_evidence_references=("engineering-note-synthetic-001",),
        required_actions=("synthetic_inspection",),
        estimated_ground_time_hours=4.0,
        ground_time_unavailable_reason=None,
        estimated_repair_labor_cost_usd=Decimal("125.00"),
        need_by_time=TIMESTAMP,
        parts_ready_at=TIMESTAMP,
        return_to_service_time=TIMESTAMP,
        meets_need_by_time=True,
        eta_confidence=0.75,
        risk_metrics=MaintenanceRiskMetrics(
            delay_risk=MaintenanceRiskLevel.LOW,
            parts_dependency_risk=MaintenanceRiskLevel.MEDIUM,
            repair_complexity_risk=MaintenanceRiskLevel.LOW,
        ),
        technical_risks=(),
        assumptions=(),
        missing_data=(),
        warnings=(),
        approval_evidence=EngineeringApprovalEvidence(
            status=ApprovalEvidenceStatus.APPROVAL_RECORDED,
            approver_role="maintenance_airworthiness_authority",
            source_reference="approval-record-synthetic-001",
            recorded_at=TIMESTAMP,
        ),
        recommendation=MaintenanceRecommendation(
            decision=MaintenanceRecommendationDecision.REPAIR,
            confidence=0.75,
            rationale="Synthetic contract fixture only",
            next_steps=("Retain human approval responsibility",),
        ),
    )


def materials_payload() -> MaterialsLogisticsAssessmentPayload:
    return MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.LIMITED,
        part_availability=(
            PartAvailabilityRecord(
                part_number="P-110",
                role=PartRole.FAILED_PART,
                required_quantity=1,
                available_quantity=1,
                location="TEST-STATION-A",
                source="synthetic-inventory",
                retrieved_at=TIMESTAMP,
                validity_state=EvidenceValidity.CURRENT,
                claim_reference="claim-synthetic-P110",
            ),
        ),
        part_eligibility=(
            PartEligibilityEvidence(
                part_number="P-120",
                compatibility=CompatibilityStatus.COMPATIBLE,
                authorization=AuthorizationStatus.AUTHORIZED,
                traceability=TraceabilityStatus.VERIFIED,
                checked_by_role="materials_inventory_specialist",
                evidence_references=("authorization-synthetic-001",),
            ),
        ),
        sourcing_options=(
            SourcingOption(
                part_number="P-120",
                source="synthetic-stock-location",
                source_location="TEST-STATION-B",
                method=SourcingMethod.INTERNAL_TRANSFER,
                shipping_provider=ShippingProvider.FEDEX_NETWORK,
                shipping_service="priority_freight",
                transfer_required=True,
                lead_time_hours=8.0,
                eta_at=TIMESTAMP,
                estimated_cost_usd=Decimal("250.00"),
                quote_unavailable_reason=None,
                evidence_references=("quote-synthetic-001",),
            ),
        ),
        confidence=0.8,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
    )


def test_domain_payloads_preserve_repair_and_sourcing_fields() -> None:
    maintenance = maintenance_payload()
    materials = materials_payload()

    assert maintenance.root_cause is not None
    assert maintenance.root_cause.evidence_references == ("maintenance-record-synthetic-001",)
    assert maintenance.recurring_failure is not None
    assert maintenance.recurring_failure.occurrences == 3
    assert maintenance.approval_evidence.status is ApprovalEvidenceStatus.APPROVAL_RECORDED
    assert materials.part_availability[0].validity_state is EvidenceValidity.CURRENT
    assert materials.part_eligibility[0].authorization is AuthorizationStatus.AUTHORIZED
    assert materials.sourcing_options[0].estimated_cost_usd == Decimal("250.00")


def test_maintenance_payload_rejects_missing_or_unsupported_fields() -> None:
    payload = maintenance_payload().model_dump(mode="python")
    del payload["repairability_status"]

    with pytest.raises(ValidationError):
        MaintenanceAssessmentPayload.model_validate(payload)

    payload = maintenance_payload().model_dump(mode="python")
    payload["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        MaintenanceAssessmentPayload.model_validate(payload)


def test_feasible_repair_requires_provenance_for_approval_evidence() -> None:
    payload = maintenance_payload().model_dump(mode="python")
    payload["approval_evidence"] = {
        "status": ApprovalEvidenceStatus.APPROVAL_RECORDED,
        "approver_role": None,
        "source_reference": None,
        "recorded_at": None,
    }

    with pytest.raises(ValidationError, match="recorded approval requires"):
        MaintenanceAssessmentPayload.model_validate(payload)


def test_preferred_replacement_requires_supporting_evidence() -> None:
    payload = maintenance_payload().model_dump(mode="python")
    payload["preferred_replacement_evidence_references"] = ()

    with pytest.raises(ValidationError, match="preferred replacement requires"):
        MaintenanceAssessmentPayload.model_validate(payload)


def test_unknown_and_stale_data_remain_explicit() -> None:
    payload = materials_payload().model_dump(mode="python")
    payload["availability_status"] = AvailabilityStatus.UNCERTAIN
    payload["missing_data"] = ("P-120 source inventory is stale",)
    payload["part_availability"][0]["validity_state"] = EvidenceValidity.STALE

    materials = MaterialsLogisticsAssessmentPayload.model_validate(payload)

    assert materials.availability_status is AvailabilityStatus.UNCERTAIN
    assert materials.part_availability[0].validity_state is EvidenceValidity.STALE
    assert materials.missing_data == ("P-120 source inventory is stale",)


def test_material_payload_rejects_invalid_quantity_and_quote_defaults() -> None:
    payload = materials_payload().model_dump(mode="python")
    payload["part_availability"][0]["available_quantity"] = -1

    with pytest.raises(ValidationError):
        MaterialsLogisticsAssessmentPayload.model_validate(payload)

    payload = materials_payload().model_dump(mode="python")
    payload["sourcing_options"][0]["estimated_cost_usd"] = None
    payload["sourcing_options"][0]["quote_unavailable_reason"] = None
    with pytest.raises(ValidationError, match="missing quote values"):
        MaterialsLogisticsAssessmentPayload.model_validate(payload)


def test_known_part_eligibility_requires_provenance() -> None:
    payload = materials_payload().model_dump(mode="python")
    payload["part_eligibility"][0]["evidence_references"] = ()

    with pytest.raises(ValidationError, match="known eligibility states require"):
        MaterialsLogisticsAssessmentPayload.model_validate(payload)
