import json
from datetime import UTC, datetime
from pathlib import Path

from aog_recovery.contracts.evidence import EvidenceValidity
from aog_recovery.controller.candidates import build_recovery_candidates
from aog_recovery.controller.models import CandidateBuildContext
from aog_recovery.materials_logistics.agent import MaterialsLogisticsAssessmentInput
from aog_recovery.operations.models import OptionKind

FIXTURE_ROOT = Path("incidents/mock_data")
EVALUATED_AT = datetime(2026, 10, 22, 10, 10, tzinfo=UTC)


def materials_input(scenario_id: str) -> MaterialsLogisticsAssessmentInput:
    document = json.loads(
        (FIXTURE_ROOT / "materials_logistics_agent.json").read_text(encoding="utf-8")
    )
    scenario = next(item for item in document["scenarios"] if item["scenario_id"] == scenario_id)
    return MaterialsLogisticsAssessmentInput.model_validate_json(json.dumps(scenario["input"]))


def build_context(
    scenario_id: str,
    *,
    assessment=None,
    repair_hours: float | None = 3.0,
) -> CandidateBuildContext:
    payload = materials_input(scenario_id)
    return CandidateBuildContext(
        schema_version="1.0",
        case=payload.case,
        request_id=f"REQ-{scenario_id}",
        evaluated_at=EVALUATED_AT,
        failed_part_number="P-110",
        preferred_replacement_part="P-120",
        estimated_repair_duration_hours=repair_hours,
        maintenance_evidence_references=("MNT-HISTORY-1042",),
        materials_assessment=(assessment if assessment is not None else payload.assessment),
    )


def test_local_part_candidate_uses_local_source_and_computed_repair_eta() -> None:
    plans = build_recovery_candidates(build_context("part_available_local"))
    repair = next(plan for plan in plans if plan.option.kind is OptionKind.REPAIR_ALTERNATE)

    assert repair.part_number == "P-120"
    assert repair.sourcing_option is not None
    assert repair.sourcing_option.source_location == "MIA"
    assert repair.option.readiness_eta == datetime(2026, 10, 22, 13, 30, tzinfo=UTC)
    assert repair.option.eta_basis is not None


def test_remote_part_candidate_keeps_remote_location_and_transfer_eta() -> None:
    plans = build_recovery_candidates(build_context("part_available_remote"))
    repair = next(plan for plan in plans if plan.option.kind is OptionKind.REPAIR_ALTERNATE)

    assert repair.part_number == "P-120"
    assert repair.sourcing_option is not None
    assert repair.sourcing_option.source_location == "DFW"
    assert repair.option.readiness_eta == datetime(2026, 10, 22, 16, 0, tzinfo=UTC)


def test_unavailable_part_offers_swap_and_delay_without_fabricating_repair() -> None:
    plans = build_recovery_candidates(build_context("part_unavailable"))

    assert {plan.option.kind for plan in plans} == {OptionKind.SWAP, OptionKind.DELAY}
    assert all(plan.option.readiness_eta is None for plan in plans)
    assert all(plan.option.eta_evidence_references == () for plan in plans)


def test_missing_materials_or_repair_duration_remains_visible() -> None:
    no_materials = build_recovery_candidates(
        build_context("part_available_remote", assessment=None).model_copy(
            update={"materials_assessment": None}
        )
    )
    swap = next(plan for plan in no_materials if plan.option.kind is OptionKind.SWAP)
    assert "materials_assessment" in swap.missing_data

    no_duration = build_recovery_candidates(
        build_context("part_available_remote", repair_hours=None)
    )
    repair = next(plan for plan in no_duration if plan.option.kind is OptionKind.REPAIR_ALTERNATE)
    assert repair.option.readiness_eta is None
    assert "estimated_repair_duration_hours" in repair.missing_data


def test_stale_inventory_is_retained_as_warning_on_candidate() -> None:
    payload = materials_input("part_available_remote")
    stale_records = tuple(
        record.model_copy(update={"validity_state": EvidenceValidity.STALE})
        if record.part_number == "P-120"
        else record
        for record in payload.assessment.part_availability
    )
    stale_assessment = payload.assessment.model_copy(update={"part_availability": stale_records})
    plans = build_recovery_candidates(
        build_context("part_available_remote", assessment=stale_assessment)
    )
    repair = next(plan for plan in plans if plan.option.kind is OptionKind.REPAIR_ALTERNATE)

    assert repair.option.readiness_eta is not None
    assert any("stale" in warning for warning in repair.warnings)
