from datetime import UTC, datetime, timedelta
from decimal import Decimal

from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.materials_logistics.availability import evaluate_materials_availability
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


def inventory_record(
    *,
    part_number: str = "P-110",
    location: str | None = "TEST-STATION-A",
    quantity: int = 5,
    threshold: int | None = 1,
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
) -> PartAvailabilityRecord:
    return PartAvailabilityRecord(
        part_number=part_number,
        role=PartRole.ALTERNATE,
        required_quantity=2,
        available_quantity=quantity,
        minimum_stock_threshold=threshold,
        location=location,
        source="synthetic-inventory",
        retrieved_at=TIMESTAMP,
        validity_state=validity,
        claim_reference=f"inventory-claim-{part_number}",
    )


def eligibility(
    *,
    part_number: str = "P-110",
    compatibility: CompatibilityStatus = CompatibilityStatus.COMPATIBLE,
    authorization: AuthorizationStatus = AuthorizationStatus.AUTHORIZED,
    traceability: TraceabilityStatus = TraceabilityStatus.VERIFIED,
) -> PartEligibilityEvidence:
    return PartEligibilityEvidence(
        part_number=part_number,
        compatibility=compatibility,
        authorization=authorization,
        traceability=traceability,
        checked_by_role="materials_inventory_specialist",
        evidence_references=(f"eligibility-evidence-{part_number}",),
    )


def payload(
    record: PartAvailabilityRecord,
    eligibility_record: PartEligibilityEvidence | None = None,
    sourcing_options: tuple[SourcingOption, ...] = (),
) -> MaterialsLogisticsAssessmentPayload:
    return MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.UNCERTAIN,
        part_availability=(record,),
        part_eligibility=(eligibility_record,) if eligibility_record is not None else (),
        sourcing_options=sourcing_options,
        confidence=0.8,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
    )


def transfer_option(eta_at: datetime) -> SourcingOption:
    return SourcingOption(
        part_number="P-110",
        source="synthetic-transfer-source",
        source_location="TEST-STATION-B",
        method=SourcingMethod.INTERNAL_TRANSFER,
        shipping_provider=ShippingProvider.FEDEX_NETWORK,
        shipping_service="priority_freight",
        transfer_required=True,
        lead_time_hours=8.0,
        eta_at=eta_at,
        estimated_cost_usd=Decimal("250.00"),
        quote_unavailable_reason=None,
        evidence_references=("transfer-quote-001",),
    )


def test_physical_stock_at_another_station_is_not_practical_after_need_by() -> None:
    result = evaluate_materials_availability(
        payload(
            inventory_record(location="TEST-STATION-B"),
            eligibility(),
            (transfer_option(TIMESTAMP + timedelta(hours=3)),),
        ),
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP + timedelta(hours=2),
    )

    part = result.parts[0]
    assert part.physically_available is True
    assert part.practically_available is False
    assert part.location_consistent is False
    assert part.availability_status is AvailabilityStatus.UNAVAILABLE
    assert result.availability_status is AvailabilityStatus.UNAVAILABLE
    assert "transfer_outside_need_by_window" in part.findings
    assert "transfer-quote-001" in part.evidence_references


def test_local_stock_above_threshold_is_available_and_eligible() -> None:
    result = evaluate_materials_availability(
        payload(inventory_record(), eligibility()),
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP + timedelta(hours=2),
    )

    part = result.parts[0]
    assert result.availability_status is AvailabilityStatus.AVAILABLE
    assert part.practical_quantity == 4
    assert part.practically_available is True
    assert part.eligible is True


def test_failed_part_is_not_treated_as_an_alternate_eligibility_candidate() -> None:
    record = inventory_record().model_copy(update={"role": PartRole.FAILED_PART})
    result = evaluate_materials_availability(
        payload(record),
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP,
    )

    assert result.parts[0].eligible is None
    assert "eligibility_evidence_missing" not in result.parts[0].findings


def test_unknown_threshold_or_unknown_alternate_never_becomes_eligible() -> None:
    result = evaluate_materials_availability(
        payload(
            inventory_record(threshold=None),
            eligibility(
                authorization=AuthorizationStatus.UNKNOWN,
                traceability=TraceabilityStatus.UNKNOWN,
            ),
        ),
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP + timedelta(hours=2),
    )

    part = result.parts[0]
    assert part.physically_available is True
    assert part.practically_available is None
    assert part.availability_status is AvailabilityStatus.UNCERTAIN
    assert part.eligible is False
    assert "minimum_stock_threshold_unknown" in part.findings
    assert "authorization_unknown" in part.findings
    assert "traceability_unknown" in part.findings


def test_unauthorized_or_incompatible_alternate_never_becomes_eligible() -> None:
    for eligibility_record in (
        eligibility(authorization=AuthorizationStatus.UNAUTHORIZED),
        eligibility(compatibility=CompatibilityStatus.INCOMPATIBLE),
        eligibility(traceability=TraceabilityStatus.NOT_VERIFIED),
    ):
        result = evaluate_materials_availability(
            payload(inventory_record(), eligibility_record),
            target_station="TEST-STATION-A",
            need_by_time=TIMESTAMP + timedelta(hours=2),
        )

        assert result.parts[0].eligible is False


def test_inventory_below_minimum_threshold_is_limited() -> None:
    result = evaluate_materials_availability(
        payload(inventory_record(quantity=2, threshold=1), eligibility()),
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP + timedelta(hours=2),
    )

    assert result.parts[0].physically_available is True
    assert result.parts[0].practical_quantity == 1
    assert result.parts[0].practically_available is False
    assert result.availability_status is AvailabilityStatus.LIMITED


def test_stale_inventory_remains_uncertain_despite_physical_quantity() -> None:
    result = evaluate_materials_availability(
        payload(inventory_record(validity=EvidenceValidity.STALE), eligibility()),
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP + timedelta(hours=2),
    )

    assert result.parts[0].physically_available is True
    assert result.parts[0].availability_status is AvailabilityStatus.UNCERTAIN
    assert "inventory_evidence_stale" in result.parts[0].findings
