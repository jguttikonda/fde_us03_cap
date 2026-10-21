from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

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
    SourcingQuoteInput,
    TraceabilityStatus,
)
from aog_recovery.materials_logistics.sourcing import (
    calculate_sourcing_option,
    compare_requested_parts,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def quote(
    *,
    method: SourcingMethod = SourcingMethod.INTERNAL_TRANSFER,
    provider: ShippingProvider | None = ShippingProvider.FEDEX_NETWORK,
    service: str | None = "priority_freight",
    unit_cost: Decimal | None = Decimal("100.00"),
    transport_cost: Decimal | None = Decimal("25.00"),
    handling_cost: Decimal | None = Decimal("5.00"),
    lead_time_hours: float | None = 3.0,
) -> SourcingQuoteInput:
    return SourcingQuoteInput(
        part_number="P-120",
        source="synthetic-source",
        source_location="TEST-STATION-B",
        method=method,
        shipping_provider=provider,
        shipping_service=service,
        transfer_required=True,
        requested_at=TIMESTAMP,
        quantity=2,
        unit_cost_usd=unit_cost,
        transport_cost_usd=transport_cost,
        handling_cost_usd=handling_cost,
        lead_time_hours=lead_time_hours,
        evidence_references=("quote-evidence-001",),
        assumptions=("synthetic mock USD quote",),
    )


def test_quote_arithmetic_is_deterministic_and_preserves_source_assumptions() -> None:
    option = calculate_sourcing_option(quote())

    assert option.estimated_cost_usd == Decimal("230.00")
    assert option.eta_at == TIMESTAMP + timedelta(hours=3)
    assert option.source == "synthetic-source"
    assert option.evidence_references == ("quote-evidence-001",)
    assert option.assumptions == ("synthetic mock USD quote",)
    assert option.quote_unavailable_reason is None


@pytest.mark.parametrize(
    ("method", "provider", "service"),
    (
        (SourcingMethod.INTERNAL_TRANSFER, ShippingProvider.FEDEX_NETWORK, "priority_freight"),
        (SourcingMethod.BORROW_POOL, ShippingProvider.COMMERCIAL_CARRIER, "ground"),
        (SourcingMethod.VENDOR_PURCHASE, ShippingProvider.COMMERCIAL_CARRIER, "air"),
        (SourcingMethod.EXPEDITE, ShippingProvider.FEDEX_NETWORK, "courier"),
    ),
)
def test_sourcing_paths_keep_method_and_carrier_separate(
    method: SourcingMethod,
    provider: ShippingProvider,
    service: str,
) -> None:
    option = calculate_sourcing_option(quote(method=method, provider=provider, service=service))

    assert option.method is method
    assert option.shipping_provider is provider
    assert option.shipping_service == service


def test_unknown_cost_and_lead_time_remain_unknown_without_defaults() -> None:
    option = calculate_sourcing_option(
        quote(unit_cost=None, transport_cost=None, lead_time_hours=None)
    )

    assert option.estimated_cost_usd is None
    assert option.eta_at is None
    assert option.quote_unavailable_reason is not None
    assert "unit_cost_usd" in option.quote_unavailable_reason
    assert "transport_cost_usd" in option.quote_unavailable_reason
    assert "lead_time_hours" in option.quote_unavailable_reason


def test_shipping_service_requires_a_provider() -> None:
    with pytest.raises(ValidationError, match="shipping service requires a provider"):
        quote(provider=None)


def test_failed_and_preferred_parts_are_compared_without_omitting_missing_data() -> None:
    part = PartAvailabilityRecord(
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
    eligibility = PartEligibilityEvidence(
        part_number="P-110",
        compatibility=CompatibilityStatus.COMPATIBLE,
        authorization=AuthorizationStatus.AUTHORIZED,
        traceability=TraceabilityStatus.VERIFIED,
        checked_by_role="materials_inventory_specialist",
        evidence_references=("eligibility-P110",),
    )
    payload = MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.UNCERTAIN,
        part_availability=(part,),
        part_eligibility=(eligibility,),
        sourcing_options=(),
        confidence=0.8,
        risk_factors=(),
        assumptions=(),
        missing_data=(),
    )
    assessment = evaluate_materials_availability(
        payload,
        target_station="TEST-STATION-A",
        need_by_time=TIMESTAMP,
    )

    comparison = compare_requested_parts(assessment, "P-110", "P-120")

    assert (
        comparison.failed_part_assessments[0].availability_status is AvailabilityStatus.UNAVAILABLE
    )
    assert comparison.preferred_part_assessments == ()
    assert comparison.missing_part_numbers == ("P-120",)
