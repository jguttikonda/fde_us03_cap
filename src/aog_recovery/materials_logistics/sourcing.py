"""Deterministic sourcing quote arithmetic and requested-part comparison (ARD-MLG-005..006/009)."""

from datetime import timedelta
from decimal import Decimal

from aog_recovery.materials_logistics.models import (
    MaterialsDeterministicAssessment,
    RequestedPartComparison,
    SourcingOption,
    SourcingQuoteInput,
)


def calculate_sourcing_option(quote: SourcingQuoteInput) -> SourcingOption:
    cost_inputs = {
        "unit_cost_usd": quote.unit_cost_usd,
        "transport_cost_usd": quote.transport_cost_usd,
        "handling_cost_usd": quote.handling_cost_usd,
    }
    missing_inputs = [name for name, value in cost_inputs.items() if value is None]
    estimated_cost: Decimal | None = None
    if (
        quote.unit_cost_usd is not None
        and quote.transport_cost_usd is not None
        and quote.handling_cost_usd is not None
    ):
        estimated_cost = (
            quote.unit_cost_usd * quote.quantity
            + quote.transport_cost_usd
            + quote.handling_cost_usd
        )

    eta_at = (
        quote.requested_at + timedelta(hours=quote.lead_time_hours)
        if quote.lead_time_hours is not None
        else None
    )
    if quote.lead_time_hours is None:
        missing_inputs.append("lead_time_hours")

    return SourcingOption(
        part_number=quote.part_number,
        source=quote.source,
        source_location=quote.source_location,
        method=quote.method,
        shipping_provider=quote.shipping_provider,
        shipping_service=quote.shipping_service,
        transfer_required=quote.transfer_required,
        lead_time_hours=quote.lead_time_hours,
        eta_at=eta_at,
        estimated_cost_usd=estimated_cost,
        quote_unavailable_reason=(
            f"Missing supported quote inputs: {', '.join(missing_inputs)}"
            if missing_inputs
            else None
        ),
        evidence_references=quote.evidence_references,
        assumptions=quote.assumptions,
    )


def compare_requested_parts(
    assessment: MaterialsDeterministicAssessment,
    failed_part_number: str,
    preferred_part_number: str | None,
) -> RequestedPartComparison:
    failed_assessments = tuple(
        part for part in assessment.parts if part.part_number == failed_part_number
    )
    preferred_assessments = tuple(
        part
        for part in assessment.parts
        if preferred_part_number is not None and part.part_number == preferred_part_number
    )
    missing_part_numbers = []
    if not failed_assessments:
        missing_part_numbers.append(failed_part_number)
    if preferred_part_number is not None and not preferred_assessments:
        missing_part_numbers.append(preferred_part_number)
    return RequestedPartComparison(
        failed_part_number=failed_part_number,
        failed_part_assessments=failed_assessments,
        preferred_part_number=preferred_part_number,
        preferred_part_assessments=preferred_assessments,
        missing_part_numbers=tuple(missing_part_numbers),
    )
