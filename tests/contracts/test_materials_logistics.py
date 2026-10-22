from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.materials_logistics.models import (
    AuthorizationStatus,
    AvailabilityStatus,
    CompatibilityStatus,
    MaterialsLogisticsAssessmentPayload,
    PartAvailabilityRecord,
    PartEligibilityEvidence,
    PartRole,
    SourcingMethod,
    SourcingOption,
    TraceabilityStatus,
)

TIMESTAMP = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)


def availability_record() -> PartAvailabilityRecord:
    return PartAvailabilityRecord(
        part_number="P-110",
        role=PartRole.FAILED_PART,
        required_quantity=1,
        available_quantity=2,
        minimum_stock_threshold=None,
        location="TEST-STATION-A",
        source="synthetic-inventory",
        retrieved_at=TIMESTAMP,
        validity_state=EvidenceValidity.CURRENT,
        claim_reference="inventory-claim-P110",
    )


def materials_payload() -> MaterialsLogisticsAssessmentPayload:
    return MaterialsLogisticsAssessmentPayload(
        schema_version="1.0",
        availability_status=AvailabilityStatus.UNCERTAIN,
        part_availability=(availability_record(),),
        part_eligibility=(
            PartEligibilityEvidence(
                part_number="P-110",
                compatibility=CompatibilityStatus.UNKNOWN,
                authorization=AuthorizationStatus.UNKNOWN,
                traceability=TraceabilityStatus.UNKNOWN,
                checked_by_role=None,
                evidence_references=(),
            ),
        ),
        sourcing_options=(),
        confidence=0.6,
        risk_factors=(),
        assumptions=(),
        missing_data=("minimum stock threshold",),
    )


def test_versioned_contract_preserves_unknown_threshold_and_eligibility() -> None:
    payload = materials_payload()

    assert payload.schema_version == "1.0"
    assert payload.part_availability[0].minimum_stock_threshold is None
    assert payload.part_eligibility[0].authorization is AuthorizationStatus.UNKNOWN
    assert payload.missing_data == ("minimum stock threshold",)


def test_contract_rejects_invalid_quantity_and_unsupported_schema() -> None:
    payload = materials_payload().model_dump(mode="python")
    payload["part_availability"][0]["available_quantity"] = -1

    with pytest.raises(ValidationError):
        MaterialsLogisticsAssessmentPayload.model_validate(payload)

    payload = materials_payload().model_dump(mode="python")
    payload["schema_version"] = "2.0"
    with pytest.raises(ValidationError):
        MaterialsLogisticsAssessmentPayload.model_validate(payload)


def test_known_eligibility_requires_source_references() -> None:
    with pytest.raises(ValidationError, match="known eligibility states require"):
        PartEligibilityEvidence(
            part_number="P-120",
            compatibility=CompatibilityStatus.COMPATIBLE,
            authorization=AuthorizationStatus.AUTHORIZED,
            traceability=TraceabilityStatus.VERIFIED,
            checked_by_role="materials_inventory_specialist",
            evidence_references=(),
        )


def test_incomplete_quote_requires_reason_instead_of_a_cost_default() -> None:
    with pytest.raises(ValidationError, match="missing quote values"):
        SourcingOption(
            part_number="P-120",
            source="synthetic-vendor",
            source_location=None,
            method=SourcingMethod.VENDOR_PURCHASE,
            shipping_provider=None,
            shipping_service=None,
            transfer_required=False,
            lead_time_hours=None,
            eta_at=None,
            estimated_cost_usd=Decimal("0"),
            quote_unavailable_reason=None,
            evidence_references=(),
        )
