from decimal import Decimal
from math import ceil
from typing import Annotated

from pydantic import Field, StringConstraints

from aog_recovery.contracts.base import ContractModel
from aog_recovery.operations.contracts import (
    CostEstimate,
    CostLineItem,
    CurrencyCode,
    ImpactLevel,
    RecoveryCandidate,
    RecoveryOptionKind,
)
from aog_recovery.operations.validation import ImpactThresholds, OperationalFlight

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
NonNegativeMoney = Annotated[Decimal, Field(ge=Decimal("0"))]


class OptionCostRates(ContractModel):
    currency: CurrencyCode
    delay_per_minute: NonNegativeMoney | None
    swap_flat_cost: NonNegativeMoney | None
    unprotected_package_exposure: NonNegativeMoney | None


class CandidateImpact(ContractModel):
    option_id: NonEmptyString
    delay_minutes: Annotated[int, Field(ge=0)]
    impact_level: ImpactLevel


def estimate_delay_minutes(
    candidate: RecoveryCandidate,
    affected_flights: tuple[OperationalFlight, ...],
) -> int:
    if candidate.kind is RecoveryOptionKind.DELAY:
        return candidate.delay_minutes or 0
    if candidate.kind is RecoveryOptionKind.SWAP:
        return candidate.delay_minutes or 0
    if candidate.repair_eta is None:
        return 0
    delays = tuple(
        max(0, ceil((candidate.repair_eta - flight.departure_at).total_seconds() / 60))
        for flight in affected_flights
    )
    return max(delays, default=0)


def assess_candidate_impact(
    candidate: RecoveryCandidate,
    affected_flights: tuple[OperationalFlight, ...],
    thresholds: ImpactThresholds,
    route_disruption_delay_minutes: int = 0,
) -> CandidateImpact:
    delay_minutes = max(
        estimate_delay_minutes(candidate, affected_flights),
        route_disruption_delay_minutes,
    )
    return CandidateImpact(
        option_id=candidate.option_id,
        delay_minutes=delay_minutes,
        impact_level=thresholds.classify(delay_minutes),
    )


def estimate_option_cost(
    candidate: RecoveryCandidate,
    delay_minutes: int,
    unprotected_package_count: int | None,
    rates: OptionCostRates,
) -> CostEstimate:
    if delay_minutes < 0:
        raise ValueError("delay_minutes must be non-negative")
    if unprotected_package_count is not None and unprotected_package_count < 0:
        raise ValueError("unprotected_package_count must be non-negative")
    line_items: list[CostLineItem] = []
    missing: list[str] = []

    if candidate.kind is RecoveryOptionKind.SWAP:
        if rates.swap_flat_cost is None:
            missing.append("swap-flat-cost-rate")
        else:
            line_items.append(
                CostLineItem(
                    description="Aircraft swap",
                    amount=rates.swap_flat_cost,
                    currency=rates.currency,
                )
            )

    if delay_minutes > 0:
        if rates.delay_per_minute is None:
            missing.append("delay-cost-per-minute")
        else:
            line_items.append(
                CostLineItem(
                    description="Estimated delay",
                    amount=rates.delay_per_minute * delay_minutes,
                    currency=rates.currency,
                )
            )

    if unprotected_package_count is None:
        missing.append("package-redistribution-evidence")
    elif unprotected_package_count > 0:
        if rates.unprotected_package_exposure is None:
            missing.append("unprotected-package-exposure-rate")
        else:
            line_items.append(
                CostLineItem(
                    description="Unprotected package exposure",
                    amount=rates.unprotected_package_exposure * unprotected_package_count,
                    currency=rates.currency,
                )
            )

    if missing:
        return CostEstimate(
            total=None,
            currency=rates.currency,
            line_items=tuple(line_items),
            unavailable_reason="One or more required cost rates are unavailable.",
            missing_evidence=tuple(missing),
        )

    total = sum((item.amount for item in line_items), Decimal("0"))
    return CostEstimate(
        total=total,
        currency=rates.currency,
        line_items=tuple(line_items),
    )
