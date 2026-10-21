"""ADK web entry point: Operations Agent over deterministic synthetic data (no live systems)."""

from typing import Any

from aog_recovery.operations.adk_agent import build_operations_adk_agent
from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import OperationsOutcome
from aog_recovery.operations.prompts import OPERATIONS_INSTRUCTION
from aog_recovery.operations.synthetic import SCENARIOS, default_adapters

_DEMO_NOTE = """
Demo mode: for quick tests, call `list_demo_scenarios` to see built-in synthetic scenarios and
`run_demo_scenario` with a scenario name to assess one. Explain the structured result in plain
business language, quote its numbers exactly, and always state that human approval is required.
"""


def list_demo_scenarios() -> dict[str, str]:
    """List built-in synthetic AOG scenarios as {name: title}."""
    return {name: build().title for name, build in SCENARIOS.items()}


def run_demo_scenario(name: str) -> dict[str, Any]:
    """Run one built-in synthetic scenario through the Operations assessment (read-only).

    Args:
        name: Scenario name from `list_demo_scenarios`.

    Returns:
        The structured Operations result, or an error listing the valid names.
    """
    if name not in SCENARIOS:
        return {"error": f"unknown scenario '{name}'", "valid_names": sorted(SCENARIOS)}
    scenario = SCENARIOS[name]()
    outcome: OperationsOutcome = OperationsAgent(scenario.adapters).assess(scenario.request)
    return outcome.result.model_dump(mode="json")


root_agent = build_operations_adk_agent(OperationsAgent(default_adapters()))
root_agent.instruction = OPERATIONS_INSTRUCTION + _DEMO_NOTE
root_agent.tools = [*root_agent.tools, list_demo_scenarios, run_demo_scenario]
