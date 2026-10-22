"""Pure deterministic candidate scoring (ARD-CTL-011..014/019)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from aog_recovery.contracts.agent import AgentResultStatus
from aog_recovery.contracts.case import AogCase
from aog_recovery.controller.models import (
    CandidateHandoff,
    RecommendationCostBreakdown,
    RecommendationFactorScores,
    ScoredRecoveryOption,
    UnscoredRecoveryOption,
)
from aog_recovery.maintenance.models import (
    MaintenanceAssessmentPayload,
    MaintenanceRiskLevel,
    MaintenanceRiskMetrics,
    RepairabilityStatus,
)
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAgentPayload
from aog_recovery.operations.models import (
    ImpactLevel,
    OptionKind,
    PackageOutcome,
    RecoveryOptionAssessment,
    Viability,
)
from aog_recovery.validation.boundaries import validate_contract_json

_REPAIR_KINDS = frozenset({OptionKind.REPAIR_ORIGINAL, OptionKind.REPAIR_ALTERNATE})
_IMPACT_SCORES = {
    ImpactLevel.LOW: Decimal("100"),
    ImpactLevel.MEDIUM: Decimal("66.67"),
    ImpactLevel.HIGH: Decimal("33.33"),
    ImpactLevel.CRITICAL: Decimal("0"),
}
_RISK_SCORES = {
    MaintenanceRiskLevel.LOW: Decimal("100"),
    MaintenanceRiskLevel.MEDIUM: Decimal("50"),
    MaintenanceRiskLevel.HIGH: Decimal("0"),
}
_WEIGHT_SPEED = Decimal("0.30")
_WEIGHT_IMPACT = Decimal("0.30")
_WEIGHT_RISK = Decimal("0.30")
_WEIGHT_COST = Decimal("0.10")


@dataclass(frozen=True, slots=True)
class CandidateScoringResult:
    scored_options: tuple[ScoredRecoveryOption, ...]
    unscored_options: tuple[UnscoredRecoveryOption, ...]


@dataclass(frozen=True, slots=True)
class _RawCandidate:
    handoff: CandidateHandoff
    elapsed_minutes: Decimal
    impact_score: Decimal
    risk_score: Decimal
    cost: RecommendationCostBreakdown
    readiness_eta: datetime
    affected_routes: tuple[str, ...]
    impact_level: ImpactLevel
    schedule_delay_minutes: int | None
    package: PackageOutcome
    maintenance_risk_metrics: MaintenanceRiskMetrics
    technical_risks: tuple[str, ...]
    operational_risks: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence_references: tuple[str, ...]
    trade_off: str


def normalize_relative(
    values: Mapping[str, Decimal],
    *,
    lower_is_better: bool,
) -> dict[str, Decimal]:
    """Normalize a case-relative factor to 0..100, treating equal values equally."""
    if not values:
        return {}
    minimum = min(values.values())
    maximum = max(values.values())
    if minimum == maximum:
        return {key: Decimal("100") for key in values}
    span = maximum - minimum
    return {
        key: ((maximum - value) if lower_is_better else (value - minimum)) * Decimal("100") / span
        for key, value in values.items()
    }


def score_candidates(
    case: AogCase,
    candidates: tuple[CandidateHandoff, ...],
) -> CandidateScoringResult:
    """Score only compliant candidates with complete, validated numeric inputs."""
    raw_candidates: list[_RawCandidate] = []
    unscored: list[UnscoredRecoveryOption] = []
    for handoff in candidates:
        if not handoff.eligible:
            continue
        raw, reasons = _extract_raw_candidate(case, handoff)
        if raw is None:
            unscored.append(_unscored_option(handoff, reasons))
        else:
            raw_candidates.append(raw)

    speed_scores = normalize_relative(
        {item.handoff.result.candidate.option_id: item.elapsed_minutes for item in raw_candidates},
        lower_is_better=True,
    )
    cost_scores = normalize_relative(
        {item.handoff.result.candidate.option_id: item.cost.total_usd for item in raw_candidates},
        lower_is_better=True,
    )

    scored: list[ScoredRecoveryOption] = []
    for item in raw_candidates:
        option = item.handoff.result.candidate
        factors = RecommendationFactorScores(
            speed=speed_scores[option.option_id],
            operational_package_impact=item.impact_score,
            risk=item.risk_score,
            cost=cost_scores[option.option_id],
        )
        aggregate = (
            factors.speed * _WEIGHT_SPEED
            + factors.operational_package_impact * _WEIGHT_IMPACT
            + factors.risk * _WEIGHT_RISK
            + factors.cost * _WEIGHT_COST
        )
        scored.append(
            ScoredRecoveryOption(
                option_id=option.option_id,
                kind=option.kind,
                description=option.description,
                sourcing_method=option.sourcing_method,
                readiness_eta=item.readiness_eta,
                affected_routes=item.affected_routes,
                impact_level=item.impact_level,
                schedule_delay_minutes=item.schedule_delay_minutes,
                package=item.package,
                maintenance_risk_metrics=item.maintenance_risk_metrics,
                technical_risks=item.technical_risks,
                operational_risks=item.operational_risks,
                assumptions=item.assumptions,
                factor_scores=factors,
                aggregate_score=aggregate,
                cost=item.cost,
                evidence_references=item.evidence_references,
                trade_off=item.trade_off,
            )
        )
    return CandidateScoringResult(tuple(scored), tuple(unscored))


def _extract_raw_candidate(
    case: AogCase,
    handoff: CandidateHandoff,
) -> tuple[_RawCandidate | None, tuple[str, ...]]:
    result = handoff.result
    option = result.candidate
    reasons: list[str] = []
    if option.readiness_eta is None:
        return None, ("readiness_eta",)
    maintenance_result = result.maintenance_result
    materials_result = result.materials_logistics_result
    operations_outcome = result.operations_result
    if maintenance_result is None or maintenance_result.status is AgentResultStatus.FAILED:
        reasons.append("maintenance_result")
    if materials_result is None or materials_result.status is AgentResultStatus.FAILED:
        reasons.append("materials_logistics_result")
    if (
        operations_outcome is None
        or operations_outcome.result.status is AgentResultStatus.FAILED
        or operations_outcome.assessment is None
    ):
        reasons.append("operations_result")
    if reasons:
        return None, tuple(reasons)
    assert maintenance_result is not None
    assert materials_result is not None
    assert operations_outcome is not None
    operations_assessment = operations_outcome.assessment
    if operations_assessment is None:
        return None, ("operations_result",)

    maintenance, maintenance_report = validate_contract_json(
        MaintenanceAssessmentPayload,
        maintenance_result.role_payload,
    )
    if maintenance is None:
        return None, (f"maintenance_payload_invalid:{len(maintenance_report.findings)}",)
    materials, materials_report = validate_contract_json(
        MaterialsLogisticsAgentPayload,
        materials_result.role_payload,
    )
    if materials is None:
        return None, (f"materials_logistics_payload_invalid:{len(materials_report.findings)}",)

    assessments = tuple(
        item
        for item in operations_assessment.recovery_options
        if item.option_id == option.option_id
    )
    if len(assessments) != 1:
        return None, ("operations_candidate_assessment_missing_or_duplicated",)
    operations = assessments[0]
    if operations.viability not in {Viability.VIABLE, Viability.VIABLE_WITH_RISK}:
        return None, (f"operations_viability:{operations.viability.value}",)
    impact_score = score_operational_package_impact(operations)
    if impact_score is None:
        return None, ("operational_package_impact_unavailable",)
    risk_score = score_maintenance_risk(maintenance)
    if risk_score is None:
        return None, ("maintenance_risk_unknown",)

    repair_labor = Decimal("0")
    sourcing_cost = Decimal("0")
    if option.kind in _REPAIR_KINDS:
        if maintenance.repairability_status is not RepairabilityStatus.FEASIBLE:
            return None, ("maintenance_repairability_not_feasible",)
        if maintenance.estimated_repair_labor_cost_usd is None:
            reasons.append("repair_labor_cost")
        else:
            repair_labor = maintenance.estimated_repair_labor_cost_usd
        source_options = result.candidate_source.sourcing_options
        if len(source_options) != 1:
            reasons.append("selected_sourcing_option")
        else:
            source_option = source_options[0]
            matching_options = tuple(
                source
                for source in materials.assessment.sourcing_options
                if source == source_option
            )
            if len(matching_options) != 1:
                reasons.append("materials_sourcing_option_unverified")
            if source_option.estimated_cost_usd is None:
                reasons.append("sourcing_cost")
            else:
                sourcing_cost = source_option.estimated_cost_usd

    if operations.cost is None or not operations.cost.complete:
        reasons.append("operations_cost_incomplete")
    if reasons:
        return None, tuple(dict.fromkeys(reasons))
    assert operations.cost is not None
    assert operations.impact_level is not None

    cost = RecommendationCostBreakdown(
        repair_labor_usd=repair_labor,
        sourcing_usd=sourcing_cost,
        operations_usd=Decimal(operations.cost.total_usd),
        total_usd=repair_labor + sourcing_cost + Decimal(operations.cost.total_usd),
    )
    elapsed_minutes = _elapsed_minutes(case.created_at, option.readiness_eta)
    package = operations.package
    evidence_references = {evidence.evidence_id for evidence in result.evidence}.union(
        evidence.evidence_id for evidence in operations_outcome.evidence
    )
    evidence_references.update(maintenance_result.evidence_references)
    evidence_references.update(materials_result.evidence_references)
    evidence_references.update(option.eta_evidence_references)
    if not evidence_references:
        return None, ("score_evidence_references_missing",)
    assumptions = tuple(
        dict.fromkeys(
            (
                *maintenance.assumptions,
                *materials.assessment.assumptions,
                *operations_assessment.assumptions,
            )
        )
    )
    trade_off = (
        f"{option.description}: ETA {option.readiness_eta.isoformat()}, "
        f"{operations.schedule_delay_minutes or 0} minutes schedule impact, "
        f"{package.unprotected_count} of {package.affected_package_count} packages unprotected, "
        f"estimated USD {cost.total_usd}"
    )
    return (
        _RawCandidate(
            handoff=handoff,
            elapsed_minutes=elapsed_minutes,
            impact_score=impact_score,
            risk_score=risk_score,
            cost=cost,
            readiness_eta=option.readiness_eta,
            affected_routes=operations_assessment.affected_routes,
            impact_level=operations.impact_level,
            schedule_delay_minutes=operations.schedule_delay_minutes,
            package=operations.package,
            maintenance_risk_metrics=maintenance.risk_metrics,
            technical_risks=maintenance.technical_risks,
            operational_risks=operations_assessment.risk_factors,
            assumptions=assumptions,
            evidence_references=tuple(sorted(evidence_references)),
            trade_off=trade_off,
        ),
        (),
    )


def score_operational_package_impact(
    assessment: RecoveryOptionAssessment,
) -> Decimal | None:
    package = assessment.package
    if (
        assessment.impact_level is None
        or not package.assessed
        or package.affected_package_count is None
        or package.time_critical_package_count is None
        or package.unprotected_count is None
        or package.unprotected_time_critical_count is None
    ):
        return None
    affected = package.affected_package_count
    time_critical = package.time_critical_package_count
    unprotected = package.unprotected_count
    unprotected_time_critical = package.unprotected_time_critical_count
    if (
        time_critical > affected
        or unprotected > affected
        or unprotected_time_critical > time_critical
        or unprotected_time_critical > unprotected
    ):
        return None
    standard = affected - time_critical
    unprotected_standard = unprotected - unprotected_time_critical
    denominator = 2 * time_critical + standard
    package_score = (
        Decimal("100")
        if denominator == 0
        else Decimal("100")
        * (
            Decimal("1")
            - Decimal(2 * unprotected_time_critical + unprotected_standard) / denominator
        )
    )
    return (_IMPACT_SCORES[assessment.impact_level] + package_score) / Decimal("2")


def score_maintenance_risk(assessment: MaintenanceAssessmentPayload) -> Decimal | None:
    levels = (
        assessment.risk_metrics.delay_risk,
        assessment.risk_metrics.parts_dependency_risk,
        assessment.risk_metrics.repair_complexity_risk,
    )
    if any(level not in _RISK_SCORES for level in levels):
        return None
    return sum((_RISK_SCORES[level] for level in levels), Decimal("0")) / Decimal(len(levels))


def _elapsed_minutes(start: datetime, end: datetime) -> Decimal:
    delta = end - start
    microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
    return max(Decimal("0"), Decimal(microseconds) / Decimal("60000000"))


def _unscored_option(
    handoff: CandidateHandoff,
    reasons: tuple[str, ...],
) -> UnscoredRecoveryOption:
    result = handoff.result
    references = {evidence.evidence_id for evidence in result.evidence}
    if result.operations_result is not None:
        references.update(evidence.evidence_id for evidence in result.operations_result.evidence)
    references.update(result.candidate.eta_evidence_references)
    return UnscoredRecoveryOption(
        option_id=result.candidate.option_id,
        kind=result.candidate.kind,
        description=result.candidate.description,
        reasons=tuple(reasons),
        evidence_references=tuple(sorted(references)),
    )
