"""Thin Google ADK Controller entry point around deterministic orchestration (ARD-TEC-002)."""

from typing import Any, Literal

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from pydantic import ValidationError, model_validator

from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.controller.workflow import ControllerWorkflowPort, ControllerWorkflowResult


class ControllerAdkResponse(ContractModel):
    """Versioned ADK envelope for the deterministic Controller workflow result."""

    schema_version: Literal["1.0"]
    status: Literal["complete", "failed"]
    workflow: ControllerWorkflowResult | None = None
    failure: StructuredError | None = None

    @model_validator(mode="after")
    def require_consistent_outcome(self) -> ControllerAdkResponse:
        if self.status == "complete" and (self.workflow is None or self.failure is not None):
            raise ValueError("complete ADK response requires only a workflow result")
        if self.status == "failed" and (self.workflow is not None or self.failure is None):
            raise ValueError("failed ADK response requires only a structured failure")
        return self


CONTROLLER_INSTRUCTION = """\
You are the advisory Controller for aircraft-on-ground recovery coordination. Use the
`orchestrate_aog_recovery_case` tool to validate intake, route specialists, and obtain the
deterministic decision brief, compliance exclusions, and human-gate state. The deterministic
Controller workflow owns scoring, ranking, trade-off explanation, and report assembly. Do not
alter source values or scores, independently rank candidates, select a winner, approve a decision,
or execute an operational action. Missing, stale, conflicting, unavailable, or partial evidence
must remain visible. Both authorized human roles must approve before any operational action.
"""


def build_controller_adk_agent(
    workflow: ControllerWorkflowPort,
    *,
    model_name: str,
) -> LlmAgent:
    """Build a bounded ADK agent with only the injected deterministic orchestration tool."""

    async def orchestrate_aog_recovery_case(
        payload: dict[str, Any], tool_context: ToolContext
    ) -> dict[str, Any]:
        """Run validated advisory orchestration without ranking or operational execution.

        Args:
            payload: Versioned case, evidence, source-health, and candidate source data.

            Returns:
            Validation/routing findings, the candidate handoff, and an optional ranked decision
            brief requiring human review.
        """
        try:
            result = await workflow.run(payload)
        except Exception:
            response = _failed_response("controller_workflow_failed")
        else:
            try:
                if not isinstance(result, ControllerWorkflowResult):
                    raise TypeError("workflow returned an unexpected result type")
                validated_result = ControllerWorkflowResult.model_validate_json(
                    result.model_dump_json()
                )
            except AttributeError, TypeError, ValueError, ValidationError:
                response = _failed_response("controller_workflow_output_invalid")
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
        model=model_name,
        description=(
            "Advisory Controller: validates and coordinates candidate assessments, applies the "
            "compliance gate, ranks eligible options deterministically, and returns a decision "
            "brief for human review."
        ),
        instruction=CONTROLLER_INSTRUCTION,
        tools=[orchestrate_aog_recovery_case],
        output_schema=ControllerAdkResponse,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def _failed_response(category: str) -> ControllerAdkResponse:
    return ControllerAdkResponse(
        schema_version="1.0",
        status="failed",
        failure=StructuredError(
            schema_version="1.0",
            category=category,
            component="controller:adk-boundary",
            message="Deterministic Controller workflow did not produce a validated result",
            retryable=False,
            case_impact="The case requires deterministic Controller review",
        ),
    )
