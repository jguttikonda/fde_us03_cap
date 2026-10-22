from decimal import Decimal

import pytest

from aog_recovery.controller.models import (
    CandidateScoringInput,
    ComplianceGateResult,
    ExcludedOption,
    RecoveryCandidatePlan,
    RecoveryOptionKind,
    ScoreWeights,
)
from aog_recovery.controller.scoring import score_candidates
from aog_recovery.maintenance.models import MaintenanceRiskLevel
from aog_recovery.operations.models import CandidateOption, ImpactLevel, OptionKind


def plan(option_id: str) -> RecoveryCandidatePlan:
    return RecoveryCandidatePlan(
        option=CandidateOption(
            option_id=option_id,
            kind=OptionKind.SWAP,
            description=f"Synthetic option {option_id}",
            readiness_eta=None,
            eta_basis=None,
            eta_evidence_references=(),
        ),
        part_number=None,
        inventory_records=(),
        eligibility=None,
        sourcing_option=None,
        missing_data=(),
        warnings=(),
    )


def score_input(
    option_id: str,
    *,
    hours: float | None = 2.0,
    impact: ImpactLevel | None = ImpactLevel.LOW,
    total: int | None = 100,
    priority: int | None = 20,
    unprotected: int | None = 0,
    unprotected_priority: int | None = 0,
    risks: tuple[MaintenanceRiskLevel, ...] = (MaintenanceRiskLevel.LOW,),
    labor: Decimal | None = Decimal("1000"),
    sourcing: Decimal | None = Decimal("500"),
    operations: Decimal | None = Decimal("200"),
) -> CandidateScoringInput:
    return CandidateScoringInput(
        option_id=option_id,
        return_to_service_hours=hours,
        impact_level=impact,
        total_package_count=total,
        priority_package_count=priority,
        unprotected_package_count=unprotected,
        unprotected_priority_package_count=unprotected_priority,
        maintenance_risk_levels=risks,
        risk_factors=("Synthetic maintenance risk metric",),
        repair_labor_cost_usd=labor,
        part_and_sourcing_cost_usd=sourcing,
        operations_cost_usd=operations,
    )


def gate(*option_ids: str) -> ComplianceGateResult:
    return ComplianceGateResult(
        eligible_candidates=tuple(plan(option_id) for option_id in option_ids),
        excluded_options=(),
    )


def test_score_uses_fixed_weights_total_cost_and_stable_ranking() -> None:
    candidates = gate("OPT-A", "OPT-B")
    inputs = (
        score_input("OPT-A"),
        score_input(
            "OPT-B",
            hours=4.0,
            impact=ImpactLevel.HIGH,
            unprotected=50,
            unprotected_priority=10,
            risks=(MaintenanceRiskLevel.HIGH,),
            labor=Decimal("1000"),
            sourcing=Decimal("1000"),
            operations=Decimal("1000"),
        ),
    )

    first = score_candidates(candidates, inputs)
    second = score_candidates(candidates, inputs)

    assert first == second
    assert first.weights == ScoreWeights()
    assert first.ranked_options[0].assessment.option_id == "OPT-A"
    assert first.ranked_options[0].assessment.estimated_cost_usd == Decimal("1700")
    assert first.ranked_options[0].assessment.score_factors is not None
    factors = first.ranked_options[0].assessment.score_factors
    assert factors.speed == 100.0
    assert factors.operational_package_impact == 100.0
    assert factors.risk == 100.0
    assert factors.cost == 100.0
    assert first.ranked_options[1].assessment.aggregate_score == 24.0
    assert first.human_selection_required is False


def test_exact_two_point_top_score_gap_requires_human_selection() -> None:
    result = score_candidates(
        gate("OPT-A", "OPT-B"),
        (
            score_input("OPT-A", total=15, priority=0),
            score_input("OPT-B", total=15, priority=0, unprotected=2),
        ),
    )

    assert [item.assessment.aggregate_score for item in result.ranked_options] == [100.0, 98.0]
    assert result.human_selection_required is True
    assert result.close_score_option_ids == ("OPT-A", "OPT-B")


def test_missing_metrics_are_unscored_not_replaced_with_defaults() -> None:
    result = score_candidates(
        gate("OPT-INCOMPLETE"),
        (
            score_input(
                "OPT-INCOMPLETE",
                hours=None,
                impact=None,
                total=None,
                priority=None,
                unprotected=None,
                unprotected_priority=None,
                risks=(),
                labor=None,
                sourcing=None,
                operations=None,
            ),
        ),
    )

    assert result.ranked_options == ()
    assert len(result.unscored_options) == 1
    assert result.unscored_options[0].option_id == "OPT-INCOMPLETE"
    assert "return_to_service_hours" in result.unscored_options[0].missing_data
    assert "estimated_cost_components" in result.unscored_options[0].missing_data
    assert result.human_selection_required is False


def test_compliance_excluded_option_cannot_be_scored() -> None:
    excluded = ExcludedOption(
        option_id="OPT-EXCLUDED",
        kind=RecoveryOptionKind.REPAIR_ALTERNATE,
        reasons=("Part authorization is not confirmed",),
        evidence_references=(),
    )
    compliance = ComplianceGateResult(eligible_candidates=(), excluded_options=(excluded,))

    with pytest.raises(ValueError, match="cannot be scored"):
        score_candidates(compliance, (score_input("OPT-EXCLUDED"),))
