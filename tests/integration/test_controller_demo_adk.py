import json
import socket
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from aog_recovery.controller.adk_agent import ControllerAdkResponse
from aog_recovery.controller.demo import DEMO_SCENARIOS
from aog_recovery.controller.demo_adk_agent import build_controller_demo_adk_agent
from aog_recovery.controller.models import RecommendationStatus
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.validation.human_gate import HumanGateStatus


def test_controller_demo_adk_agent_has_only_typed_scenario_tool() -> None:
    settings = OperationsSettings(gemini_api_key=SecretStr("synthetic-test-credential"))

    agent = build_controller_demo_adk_agent(settings)

    assert agent.name == "controller_agent"
    assert agent.output_schema is ControllerAdkResponse
    assert len(agent.tools) == 1
    assert agent.tools[0].__name__ == "run_controller_demo_scenario"
    assert "run_controller_demo_scenario" in agent.instruction
    assert "orchestrate_aog_recovery_case" not in agent.instruction
    assert "synthetic-test-credential" not in repr(settings)
    assert "synthetic-test-credential" not in settings.model_dump_json()


def test_controller_adk_web_root_constructs_with_local_credential(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-credential")
    monkeypatch.setenv("ADK_MODEL", "test-model")

    module = run_path(
        str(Path(__file__).parents[2] / "adk_agents" / "controller_agent" / "agent.py")
    )

    root_agent = module["root_agent"]
    assert root_agent.name == "controller_agent"
    assert root_agent.output_schema is ControllerAdkResponse
    assert len(root_agent.tools) == 1


@pytest.mark.parametrize("credential", [None, "YOUR-VOCAREUM-KEY-HERE"])
def test_controller_demo_adk_startup_rejects_missing_or_placeholder_credential(
    credential: str | None,
) -> None:
    secret = SecretStr(credential) if credential is not None else None
    settings = OperationsSettings(gemini_api_key=secret)

    with pytest.raises(ValueError, match="GEMINI_API_KEY") as error:
        build_controller_demo_adk_agent(settings)

    assert credential is None or credential not in str(error.value)


@pytest.mark.asyncio
async def test_unknown_scenario_returns_typed_failure_without_echoing_input() -> None:
    agent = build_controller_demo_adk_agent(
        OperationsSettings(gemini_api_key=SecretStr("synthetic-test-credential"))
    )
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))
    unknown_name = "unrecognized-sensitive-value"

    result = await agent.tools[0](unknown_name, tool_context)
    response = ControllerAdkResponse.model_validate_json(json.dumps(result))

    assert response.status == "failed"
    assert response.workflow is None
    assert response.failure is not None
    assert response.failure.category == "unsupported_demo_scenario"
    assert all(
        name in response.failure.message
        for name in ("happy_path", "cache_degraded", "time_conflict", "close_score_choice")
    )
    assert unknown_name not in json.dumps(result)
    assert tool_context.actions.skip_summarization


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", DEMO_SCENARIOS)
async def test_adk_demo_scenarios_are_repeatable_offline_and_advisory(
    scenario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    settings = OperationsSettings(gemini_api_key=SecretStr("synthetic-test-credential"))
    agent = build_controller_demo_adk_agent(settings)
    tool_context = SimpleNamespace(actions=SimpleNamespace(skip_summarization=False))

    first_raw = await agent.tools[0](scenario.value, tool_context)
    second_raw = await agent.tools[0](scenario.value, tool_context)
    first = ControllerAdkResponse.model_validate_json(json.dumps(first_raw))
    second = ControllerAdkResponse.model_validate_json(json.dumps(second_raw))

    assert first == second
    assert first.status == "complete"
    assert first.workflow is not None
    assert first.workflow.handoff is not None
    assert first.workflow.recommendation is not None
    report = first.workflow.recommendation
    assert report.human_gate.status is HumanGateStatus.PENDING
    assert len(agent.tools) == 1
    assert agent.tools[0].__name__ == "run_controller_demo_scenario"
    assert "operational_actions" not in first_raw
    assert tool_context.actions.skip_summarization

    if scenario.value == "happy_path":
        assert report.ranked_options
        assert not report.errors
    elif scenario.value == "cache_degraded":
        assert first.workflow.intake.intake is not None
        assert any(error.category == "source_unavailable" for error in report.errors)
        assert any(warning.code == "CACHED_EVIDENCE" for warning in report.warnings)
        assert any(
            evidence.validity_state.value == "stale"
            for evidence in first.workflow.intake.intake.evidence
        )
    elif scenario.value == "time_conflict":
        assert report.conflicts
        assert report.status is RecommendationStatus.REQUIRES_ESCALATION
        assert any(warning.code == "CONFLICTING_EVIDENCE" for warning in report.warnings)
    elif scenario.value == "close_score_choice":
        assert report.requires_human_selection
        assert len(report.ranked_options) == 2
        assert tuple(option.selection_group for option in report.ranked_options) == (1, 1)
