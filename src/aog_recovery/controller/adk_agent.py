"""Thin Google ADK Controller entry point around deterministic orchestration (ARD-TEC-002)."""

from typing import Any

from google.adk.agents import LlmAgent

from aog_recovery.controller.workflow import ControllerWorkflowPort

CONTROLLER_INSTRUCTION = """\
You are the advisory Controller for aircraft-on-ground recovery coordination. Use the
`orchestrate_aog_recovery_case` tool to validate intake, route specialists, and obtain the
deterministic unranked handoff. Do not alter source values, calculate scores, rank candidates,
select a winner, approve a decision, or execute an operational action. Missing, stale, conflicting,
unavailable, or partial evidence must remain visible. Every handoff requires authorized human
approval.
"""


def build_controller_adk_agent(
    workflow: ControllerWorkflowPort,
    *,
    model_name: str,
) -> LlmAgent:
    """Build a bounded ADK agent with only the injected deterministic orchestration tool."""

    async def orchestrate_aog_recovery_case(payload: dict[str, Any]) -> dict[str, Any]:
        """Run validated advisory orchestration without ranking or operational execution.

        Args:
            payload: Versioned case, evidence, source-health, and candidate source data.

        Returns:
            Validation/routing findings and an optional unranked handoff requiring human review.
        """
        result = await workflow.run(payload)
        return result.model_dump(mode="json")

    return LlmAgent(
        name="controller_agent",
        model=model_name,
        description=(
            "Advisory Controller: validates and coordinates candidate assessments, applies the "
            "compliance gate, and returns an unranked handoff for human decision."
        ),
        instruction=CONTROLLER_INSTRUCTION,
        tools=[orchestrate_aog_recovery_case],
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
