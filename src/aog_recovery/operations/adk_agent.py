"""Google ADK definition of the Operations Agent (ARD-TEC-002, ARD-TEC-005).

The LLM is reached only through ADK. Its single tool is read-only and runs the deterministic
assessment; the model's job is bounded explanation (Prompts A/B/C), never rules or arithmetic.
Nothing here is invoked by tests; constructing the agent makes no model or network call.
"""

from typing import Any

from google.adk.agents import LlmAgent

from aog_recovery.operations.agent import OperationsAgent
from aog_recovery.operations.models import OperationsOutcome
from aog_recovery.operations.prompts import OPERATIONS_INSTRUCTION
from aog_recovery.operations.settings import OperationsSettings


def build_operations_adk_agent(
    agent: OperationsAgent,
    settings: OperationsSettings | None = None,
    *,
    require_model_credential: bool = True,
) -> LlmAgent:
    chosen = settings or OperationsSettings()
    if require_model_credential:
        chosen.require_model_credential()

    def assess_operational_impact(request: dict[str, Any]) -> dict[str, Any]:
        """Read-only deterministic Operations assessment for a validated request payload.

        Args:
            request: AOG case, affected flights, candidate recovery options, and evaluation time.

        Returns:
            The structured Operations result, or field-level validation findings.
        """
        outcome = agent.assess_payload(request)
        if isinstance(outcome, OperationsOutcome):
            return outcome.model_dump(mode="json")
        return {"status": "invalid_request", "findings": outcome.model_dump(mode="json")}

    return LlmAgent(
        name="operations_agent",
        model=chosen.adk_model,
        description=(
            "Advisory Operations Agent: assesses flight, fleet, and package impact of each "
            "AOG recovery option. Never ranks, approves, or executes."
        ),
        instruction=OPERATIONS_INSTRUCTION,
        tools=[assess_operational_impact],
    )
