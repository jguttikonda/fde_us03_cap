import json
import socket

import pytest

from aog_recovery.controller.demo import (
    DEMO_SCENARIOS,
    build_demo_intake,
    main,
    run_demo_scenario,
)
from aog_recovery.controller.demo_workflow import run_controller_demo_workflow
from aog_recovery.controller.models import ControllerIntake, RecommendationStatus
from aog_recovery.coordination.recording import ExchangeRecordingStatus
from aog_recovery.operations.models import OptionKind
from aog_recovery.validation.human_gate import HumanGateStatus


@pytest.mark.parametrize("scenario", DEMO_SCENARIOS)
def test_demo_scenarios_are_repeatable_offline_and_advisory(
    scenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", deny_network)

    first = run_demo_scenario(scenario.value)
    second = run_demo_scenario(scenario.value)

    assert first == second
    assert first.offline is True
    assert first.advisory_only is True
    assert first.operational_actions == ()
    assert first.report.human_gate.status is HumanGateStatus.PENDING


@pytest.mark.parametrize("scenario", DEMO_SCENARIOS)
def test_demo_intakes_are_typed_repeatable_and_provenance_complete(scenario) -> None:
    first = build_demo_intake(scenario)
    second = build_demo_intake(scenario)

    assert isinstance(first, ControllerIntake)
    assert first == second
    evidence_ids = {item.evidence_id for item in first.evidence}
    assert all(
        set(candidate.source_evidence_references).issubset(evidence_ids)
        for candidate in first.candidate_sources
    )
    if scenario.value == "cache_degraded":
        assert any(item.validity_state.value == "stale" for item in first.evidence)
    if scenario.value == "time_conflict":
        estimates = [
            item.content.get("estimate_hours")
            for item in first.evidence
            if item.claim_reference == "recovery-time-estimate"
        ]
        assert estimates == [3, 7]
    if scenario.value == "close_score_choice":
        assert len(first.candidate_sources) == 2
        assert len({item.source_key for item in first.candidate_sources}) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", DEMO_SCENARIOS)
async def test_full_controller_workflow_demo_scenarios_are_repeatable_and_offline(
    scenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", deny_network)

    first = await run_controller_demo_workflow(scenario)
    second = await run_controller_demo_workflow(scenario)

    assert first == second
    assert first.handoff is not None
    assert first.recommendation is not None
    assert first.recommendation.human_gate.status is HumanGateStatus.PENDING
    assert first.recommendation.trace_context == first.handoff.case.trace_context
    assert all(
        candidate.result.peer_exchange_recording is not None
        for candidate in first.handoff.candidates
    )
    assert all(
        candidate.result.peer_exchange_recording.status is ExchangeRecordingStatus.COMPLETE
        for candidate in first.handoff.candidates
        if candidate.result.peer_exchange_recording is not None
    )

    if scenario.value == "happy_path":
        assert first.recommendation.ranked_options
        assert not first.recommendation.errors
    elif scenario.value == "cache_degraded":
        assert any(error.category == "source_unavailable" for error in first.recommendation.errors)
        assert any(warning.code == "CACHED_EVIDENCE" for warning in first.recommendation.warnings)
        assert first.recommendation.confidence.confidence <= 0.49
    elif scenario.value == "time_conflict":
        assert first.recommendation.conflicts
        assert first.recommendation.status is RecommendationStatus.REQUIRES_ESCALATION
        assert any(
            warning.code == "CONFLICTING_EVIDENCE" for warning in first.recommendation.warnings
        )
    elif scenario.value == "close_score_choice":
        assert first.recommendation.requires_human_selection
        assert len(first.recommendation.ranked_options) == 2
        assert tuple(option.selection_group for option in first.recommendation.ranked_options) == (
            1,
            1,
        )


def test_happy_path_demo_has_source_backed_advisory_repair() -> None:
    result = run_demo_scenario("happy_path")

    assert len(result.report.ranked_options) == 1
    option = result.report.ranked_options[0]
    assert option.kind is OptionKind.REPAIR_ALTERNATE
    assert {"approval-evidence-001", "part-eligibility-001"}.issubset(
        set(option.evidence_references)
    )
    assert option.trade_off
    assert result.report.human_gate.status is HumanGateStatus.PENDING
    assert result.operational_actions == ()


def test_cache_degraded_demo_preserves_failure_staleness_and_escalation() -> None:
    result = run_demo_scenario("cache_degraded")
    cached = next(item for item in result.evidence if item.evidence_id == "inventory-cache-p120")

    assert result.report.status is RecommendationStatus.REQUIRES_ESCALATION
    assert result.report.confidence.confidence == 0.49
    assert result.report.ranked_options
    assert any(error.category == "source_unavailable" for error in result.report.errors)
    assert any(warning.code == "CACHED_EVIDENCE" for warning in result.report.warnings)
    assert cached.validity_state.value == "stale"
    assert cached.source == "synthetic-inventory-cache"
    assert result.report.human_gate.status is HumanGateStatus.PENDING
    assert result.operational_actions == ()


def test_time_conflict_demo_shows_both_estimates_and_defers_approval() -> None:
    result = run_demo_scenario("time_conflict")
    estimates = {
        item.source: item.content.get("estimate_hours")
        for item in result.evidence
        if item.claim_reference == "recovery-time-estimate"
    }

    assert estimates == {
        "synthetic-maintenance-estimate": 3,
        "synthetic-operations-disruption": 7,
    }
    assert result.report.conflicts
    assert set(result.report.conflicts[0].evidence_references) == {
        "maintenance-time-estimate-3h",
        "operations-disruption-estimate-7h",
    }
    assert result.report.status is RecommendationStatus.REQUIRES_ESCALATION
    assert result.report.human_gate.status is HumanGateStatus.PENDING


def test_close_score_demo_groups_both_options_for_human_selection() -> None:
    result = run_demo_scenario("close_score_choice")

    assert result.report.requires_human_selection is True
    assert len(result.report.ranked_options) == 2
    assert tuple(option.selection_group for option in result.report.ranked_options) == (1, 1)
    assert all(option.trade_off for option in result.report.ranked_options)
    assert result.report.human_gate.status is HumanGateStatus.PENDING
    assert result.operational_actions == ()


def test_cli_returns_repeatable_structured_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json", "happy_path", "cache_degraded"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert [item["scenario"] for item in output] == ["happy_path", "cache_degraded"]
    assert all(item["offline"] and item["advisory_only"] for item in output)
    assert all(item["operational_actions"] == [] for item in output)


def test_cli_rejects_unknown_scenarios(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["not-a-scenario"]) == 2
    assert "Unknown scenario" in capsys.readouterr().out
