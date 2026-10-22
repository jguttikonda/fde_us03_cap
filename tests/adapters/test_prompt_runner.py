from pydantic import Field

from aog_recovery.adk.prompt_runner import GoogleAdkPromptRunner
from aog_recovery.contracts.base import ContractModel


class StructuredOutput(ContractModel):
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)


def test_prompt_agent_uses_json_mode_and_keeps_schema_validation_local() -> None:
    agent = GoogleAdkPromptRunner("test-model").build_prompt_agent(
        agent_name="maintenance_agent",
        stage_name="evidence_grounding",
        instruction="Return the requested schema.",
        output_model=StructuredOutput,
    )

    assert agent.output_schema is None
    assert agent.generate_content_config is not None
    assert agent.generate_content_config.response_mime_type == "application/json"
    assert "additionalProperties" in agent.instruction
    assert "confidence" in agent.instruction
