"""Deterministic option scoring over compliance-approved candidates (ARD-CTL-011..015/019)."""

from collections.abc import Sequence
from decimal import Decimal

from aog_recovery.controller.models import (
    CandidateAssessment,
    CandidateScoringInput,
    ComplianceGateResult,
    RankedOption,
    RecoveryOptionKind,
    ScoreFactors,
    ScoreWeights,
    ScoringResult,
    UnscoredOption,
)
from aog_recovery.maintenance.models import MaintenanceRiskLevel
from aog_recovery.operations.models import ImpactLevel

_RISK_SCORE = {
    MaintenanceRiskLevel.LOW: 100.0,
    MaintenanceRiskLevel.MEDIUM: 65.0,
    MaintenanceRiskLevel.HIGH: 30.0,
}
_IMPACT_SCORE = {
    ImpactLevel.LOW: 100.0,
    ImpactLevel.MEDIUM: 75.0,
    ImpactLevel.HIGH: 50.0,
    ImpactLevel.CRITICAL: 25.0,
}
_WEIGHTS = ScoreWeights()


def score_candidates(
    compliance: ComplianceGateResult,
    score_inputs: tuple[CandidateScoringInput, ...],
) -> ScoringResult:
    """Score only eligible options; incomplete metrics remain explicitly unscored."""
    eligible = {
        candidate.option.option_id: candidate for candidate in compliance.eligible_candidates
    }
    excluded_ids = {item.option_id for item in compliance.excluded_options}
    metrics_by_id: dict[str, CandidateScoringInput] = {}
    for item in score_inputs:
        if item.option_id in excluded_ids:
            raise ValueError(f"excluded option '{item.option_id}' cannot be scored")
        if item.option_id not in eligible:
            raise ValueError(f"score input '{item.option_id}' is not compliance-eligible")
        if item.option_id in metrics_by_id:
            raise ValueError(f"duplicate score input for option '{item.option_id}'")
        metrics_by_id[item.option_id] = item

    complete: list[tuple[str, CandidateScoringInput, Decimal, float]] = []
    unscored: list[UnscoredOption] = []
    for option_id in eligible:
        metrics = metrics_by_id.get(option_id)
        if metrics is None:
            unscored.append(UnscoredOption(option_id=option_id, missing_data=("score_inputs",)))
            continue
        missing = _missing_score_inputs(metrics)
        if missing:
            unscored.append(UnscoredOption(option_id=option_id, missing_data=missing))
            continue
        assert metrics.repair_labor_cost_usd is not None
        assert metrics.part_and_sourcing_cost_usd is not None
        assert metrics.operations_cost_usd is not None
        assert metrics.total_package_count is not None
        assert metrics.priority_package_count is not None
        assert metrics.unprotected_package_count is not None
        assert metrics.unprotected_priority_package_count is not None
        assert metrics.impact_level is not None
        total_cost = (
            metrics.repair_labor_cost_usd
            + metrics.part_and_sourcing_cost_usd
            + metrics.operations_cost_usd
        )
        impact_score = _operational_package_score(metrics)
        complete.append((option_id, metrics, total_cost, impact_score))

    if not complete:
        return ScoringResult(
            weights=_WEIGHTS,
            ranked_options=(),
            excluded_options=compliance.excluded_options,
            unscored_options=tuple(sorted(unscored, key=lambda item: item.option_id)),
            close_score_option_ids=(),
            human_selection_required=False,
        )

    hours = [
        metrics.return_to_service_hours
        for _, metrics, _, _ in complete
        if metrics.return_to_service_hours is not None
    ]
    costs = [cost for _, _, cost, _ in complete]
    assert all(value is not None for value in hours)
    ranked: list[RankedOption] = []
    for option_id, metrics, total_cost, impact_score in complete:
        assert metrics.return_to_service_hours is not None
        speed_score = _lower_is_better_score(metrics.return_to_service_hours, hours)
        cost_score = _lower_is_better_score(total_cost, costs)
        risk_score = sum(_RISK_SCORE[level] for level in metrics.maintenance_risk_levels) / len(
            metrics.maintenance_risk_levels
        )
        factors = ScoreFactors(
            speed=round(speed_score, 2),
            operational_package_impact=round(impact_score, 2),
            risk=round(risk_score, 2),
            cost=round(cost_score, 2),
        )
        aggregate = round(
            (
                factors.speed * _WEIGHTS.speed
                + factors.operational_package_impact * _WEIGHTS.operational_package_impact
                + factors.risk * _WEIGHTS.risk
                + factors.cost * _WEIGHTS.cost
            )
            / 100.0,
            2,
        )
        plan = eligible[option_id]
        evidence_references = set(plan.option.eta_evidence_references)
        evidence_references.update(record.claim_reference for record in plan.inventory_records)
        if plan.eligibility is not None:
            evidence_references.update(plan.eligibility.evidence_references)
        if plan.sourcing_option is not None:
            evidence_references.update(plan.sourcing_option.evidence_references)
        risk_names = tuple(level.value for level in metrics.maintenance_risk_levels)
        trade_off = (
            f"Estimated return to service in {round(metrics.return_to_service_hours, 1):g} hours; "
            f"{metrics.unprotected_package_count} packages remain unprotected, including "
            f"{metrics.unprotected_priority_package_count} priority; total estimated cost "
            f"is ${total_cost:.2f}."
        )
        assessment = CandidateAssessment(
            option_id=option_id,
            kind=RecoveryOptionKind(plan.option.kind.value),
            description=plan.option.description,
            sourcing_method=plan.option.sourcing_method,
            return_to_service_hours=metrics.return_to_service_hours,
            estimated_cost_usd=total_cost,
            evidence_references=tuple(sorted(evidence_references)),
            assumptions=plan.warnings,
            risks=(*metrics.risk_factors, *risk_names),
            compliance_eligible=True,
            exclusion_reasons=(),
            score_factors=factors,
            score_weights=_WEIGHTS,
            aggregate_score=aggregate,
            trade_off=trade_off,
            sourcing_source=(
                plan.sourcing_option.source if plan.sourcing_option is not None else None
            ),
            sourcing_location=(
                plan.sourcing_option.source_location if plan.sourcing_option is not None else None
            ),
            sourcing_lead_time_hours=(
                plan.sourcing_option.lead_time_hours if plan.sourcing_option is not None else None
            ),
            affected_flight_numbers=metrics.affected_flight_numbers,
            affected_package_count=metrics.total_package_count,
            priority_package_count=metrics.priority_package_count,
            unprotected_package_count=metrics.unprotected_package_count,
            main_risk=metrics.risk_factors[0] if metrics.risk_factors else None,
        )
        ranked.append(RankedOption(rank=1, assessment=assessment))

    ranked.sort(key=lambda item: (-_aggregate_score(item), item.assessment.option_id))
    ranked = [item.model_copy(update={"rank": rank}) for rank, item in enumerate(ranked, start=1)]
    top_score = _aggregate_score(ranked[0])
    close_ids = tuple(
        item.assessment.option_id for item in ranked if top_score - _aggregate_score(item) <= 2.0
    )
    return ScoringResult(
        weights=_WEIGHTS,
        ranked_options=tuple(ranked),
        excluded_options=compliance.excluded_options,
        unscored_options=tuple(sorted(unscored, key=lambda item: item.option_id)),
        close_score_option_ids=close_ids if len(close_ids) > 1 else (),
        human_selection_required=len(close_ids) > 1,
    )


def _missing_score_inputs(metrics: CandidateScoringInput) -> tuple[str, ...]:
    missing: list[str] = []
    if metrics.return_to_service_hours is None:
        missing.append("return_to_service_hours")
    if metrics.impact_level is None:
        missing.append("impact_level")
    if any(
        value is None
        for value in (
            metrics.total_package_count,
            metrics.priority_package_count,
            metrics.unprotected_package_count,
            metrics.unprotected_priority_package_count,
        )
    ):
        missing.append("package_impact_counts")
    if not metrics.maintenance_risk_levels or any(
        level is MaintenanceRiskLevel.UNKNOWN for level in metrics.maintenance_risk_levels
    ):
        missing.append("maintenance_risk_levels")
    if any(
        value is None
        for value in (
            metrics.repair_labor_cost_usd,
            metrics.part_and_sourcing_cost_usd,
            metrics.operations_cost_usd,
        )
    ):
        missing.append("estimated_cost_components")
    return tuple(missing)


def _operational_package_score(metrics: CandidateScoringInput) -> float:
    assert metrics.impact_level is not None
    assert metrics.total_package_count is not None
    assert metrics.priority_package_count is not None
    assert metrics.unprotected_package_count is not None
    assert metrics.unprotected_priority_package_count is not None
    weighted_total = metrics.total_package_count + metrics.priority_package_count
    weighted_unprotected = (
        metrics.unprotected_package_count + metrics.unprotected_priority_package_count
    )
    package_score = (
        100.0
        if weighted_total == 0
        else 100.0 * (weighted_total - weighted_unprotected) / weighted_total
    )
    return (_IMPACT_SCORE[metrics.impact_level] + package_score) / 2.0


def _lower_is_better_score(value: float | Decimal, peers: Sequence[float | Decimal]) -> float:
    numeric_peers = [float(peer) for peer in peers]
    minimum = min(numeric_peers)
    maximum = max(numeric_peers)
    if maximum == minimum:
        return 100.0
    return 100.0 * (maximum - float(value)) / (maximum - minimum)


def _aggregate_score(option: RankedOption) -> float:
    score = option.assessment.aggregate_score
    if score is None:
        raise ValueError(f"ranked option '{option.assessment.option_id}' has no aggregate score")
    return score
