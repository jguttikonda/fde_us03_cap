import socket

import pytest

from aog_recovery.operations.adk_agent import build_operations_adk_agent
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.demo import DEFAULT_ORDER, main, run_scenario
from aog_recovery.operations.prompts import OPERATIONS_INSTRUCTION
from aog_recovery.operations.settings import OperationsSettings
from aog_recovery.operations.synthetic import SCENARIOS, scenario_normal_repair


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", blocked)


def test_adk_agent_carries_prompts_and_one_read_only_tool(no_network: None) -> None:
    scenario = scenario_normal_repair()
    agent = build_operations_adk_agent(
        OperationsAgent(scenario.adapters), OperationsSettings(adk_model="test-model")
    )
    assert type(agent).__name__ == "LlmAgent"
    assert agent.name == "operations_agent"
    assert agent.model == "test-model"
    assert agent.instruction == OPERATIONS_INSTRUCTION
    for stage in ("Stage A", "Stage B", "Stage C"):
        assert stage in agent.instruction  # type: ignore[operator]
    assert len(agent.tools) == 1
    assert getattr(agent.tools[0], "__name__", "") == "assess_operational_impact"


def test_adk_tool_runs_the_deterministic_assessment_and_rejects_bad_input(
    no_network: None,
) -> None:
    scenario = scenario_normal_repair()
    agent = build_operations_adk_agent(OperationsAgent(scenario.adapters))
    tool = agent.tools[0]
    assert callable(tool)
    good = tool(scenario.request.model_dump())
    assert good["result"]["status"] == "complete"
    assert good["result"]["role_payload"]["human_approval_required"] is True
    bad = tool({"schema_version": "9"})
    assert bad["status"] == "invalid_request"
    assert bad["findings"]["is_valid"] is False


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_demo_renders_input_and_output_offline(name: str, no_network: None) -> None:
    text = run_scenario(SCENARIOS[name]())
    assert "INPUT" in text and "OUTPUT" in text
    assert "Candidate " in text
    assert "Human approval required: True" in text or "Reason:" in text


def test_demo_json_mode_and_cli(capsys: pytest.CaptureFixture[str], no_network: None) -> None:
    assert "role_payload" in run_scenario(SCENARIOS["normal_repair"](), as_json=True)
    assert main(["swap_capacity"]) == 0
    out = capsys.readouterr().out
    assert "300 packages unprotected" in out
    assert main(["no_such_scenario"]) == 2
    assert main([]) == 0
    full = capsys.readouterr().out
    for name in DEFAULT_ORDER:
        assert SCENARIOS[name]().title in full
