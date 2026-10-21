import pytest
from pydantic import ValidationError

from aog_recovery.contracts.agent import (
    AgentResult,
    AgentRole,
    RecoveryOption,
    StructuredError,
)


def test_agent_result_accepts_common_envelope_and_role_payload(
    agent_result_payload: dict[str, object],
) -> None:
    result = AgentResult.model_validate(agent_result_payload)

    assert result.schema_version == "1.0"
    assert result.agent_role is AgentRole.MAINTENANCE
    assert result.role_payload == {"finding": "synthetic"}


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_agent_result_rejects_out_of_range_confidence(
    agent_result_payload: dict[str, object], confidence: float
) -> None:
    agent_result_payload["confidence"] = confidence

    with pytest.raises(ValidationError, match="confidence"):
        AgentResult.model_validate(agent_result_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [("schema_version", "2.0"), ("role_payload", "not an object")],
)
def test_agent_result_rejects_invalid_envelope(
    agent_result_payload: dict[str, object], field: str, value: object
) -> None:
    agent_result_payload[field] = value

    with pytest.raises(ValidationError):
        AgentResult.model_validate(agent_result_payload)


def test_structured_error_and_recovery_option_have_explicit_shapes() -> None:
    error = StructuredError(
        schema_version="1.0",
        category="source_unavailable",
        component="maintenance-adapter",
        message="Synthetic source is unavailable",
        retryable=False,
        case_impact="maintenance evidence is unavailable",
    )
    option = RecoveryOption(
        option_id="option-001",
        description="Synthetic option awaiting human review",
        evidence_references=("ev-001",),
        assumptions=(),
    )

    assert error.retryable is False
    assert option.option_id == "option-001"
    assert not hasattr(option, "score")
