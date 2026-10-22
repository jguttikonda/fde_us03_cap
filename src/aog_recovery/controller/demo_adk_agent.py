"""ADK boundary for the finite synthetic Controller demo (ARD-TEC-002/005)."""

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from pydantic import ValidationError

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.controller.adk_agent import CONTROLLER_INSTRUCTION, ControllerAdkResponse
from aog_recovery.controller.demo import DEMO_SCENARIOS, DemoScenario
from aog_recovery.controller.demo_workflow import run_controller_demo_workflow
from aog_recovery.controller.workflow import ControllerWorkflowResult
from aog_recovery.operations.settings import OperationsSettings

_DEMO_INSTRUCTION = """
Use `run_controller_demo_scenario` only with one supported scenario name. If the user's request
does not clearly identify a scenario, ask for clarification. Preserve the structured result,
including degraded evidence, conflicts, and failures. Never approve or execute an operation;
human approval remains pending.
"""


def build_controller_demo_adk_agent(
    settings: OperationsSettings | None = None,
    *,
    require_model_credential: bool = True,
) -> LlmAgent:
    """Build the Controller Web agent with only the named synthetic-scenario tool."""
    chosen = settings or OperationsSettings()
    if require_model_credential:
        chosen.require_model_credential()

    async def run_controller_demo_scenario(
        scenario_name: str, tool_context: ToolContext
    ) -> dict[str, Any]:
        """Run one fixed synthetic AOG scenario through the deterministic Controller workflow.

        Args:
            scenario_name: One of the supported names returned in a failure response.

        Returns:
            The typed Controller workflow result or a structured failure.
        """
        try:
            scenario = DemoScenario(scenario_name)
        except TypeError, ValueError:
            response = _failed_response(
                "unsupported_demo_scenario",
                "Unknown scenario name. Supported scenarios: "
                + ", ".join(scenario.value for scenario in DEMO_SCENARIOS),
            )
        else:
            try:
                result = await run_controller_demo_workflow(scenario)
            except Exception:
                response = _failed_response(
                    "controller_workflow_failed",
                    "Deterministic Controller workflow did not produce a result",
                )
            else:
                try:
                    validated_result = ControllerWorkflowResult.model_validate_json(
                        result.model_dump_json()
                    )
                except AttributeError, TypeError, ValueError, ValidationError:
                    response = _failed_response(
                        "controller_workflow_output_invalid",
                        "Deterministic Controller workflow did not produce a validated result",
                    )
                else:
                    response = ControllerAdkResponse(
                        schema_version="1.0",
                        status="complete",
                        workflow=validated_result,
                    )

        tool_context.actions.skip_summarization = True
        return response.model_dump(mode="json")

    return LlmAgent(
        name="controller_agent",
        model=chosen.adk_model,
        description=(
            "Advisory Controller demo: runs one named synthetic recovery scenario and returns "
            "the deterministic decision brief for human review."
        ),
        instruction=CONTROLLER_INSTRUCTION.replace(
            "orchestrate_aog_recovery_case", "run_controller_demo_scenario"
        )
        + _DEMO_INSTRUCTION,
        tools=[run_controller_demo_scenario],
        output_schema=ControllerAdkResponse,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def _failed_response(category: str, message: str) -> ControllerAdkResponse:
    return ControllerAdkResponse(
        schema_version="1.0",
        status="failed",
        failure=StructuredError(
            schema_version="1.0",
            category=category,
            component="controller:adk-demo-boundary",
            message=message,
            retryable=False,
            case_impact="The case requires deterministic Controller review",
        ),
    )
