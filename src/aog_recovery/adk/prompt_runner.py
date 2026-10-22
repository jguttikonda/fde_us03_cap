"""Google ADK prompt boundary for bounded, schema-validated stages (ARD-TEC-002/005)."""

import asyncio
import json
from collections.abc import Mapping
from typing import Protocol
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, ValidationError


class PromptRunner(Protocol):
    async def run_prompt(
        self,
        *,
        agent_name: str,
        stage_name: str,
        instruction: str,
        inputs: dict[str, object],
        output_model: type[BaseModel],
    ) -> BaseModel | Mapping[str, object]: ...


class PromptRunnerError(RuntimeError):
    """A bounded ADK prompt stage failed or returned invalid structured output."""


class GoogleAdkPromptRunner:
    def __init__(self, model_name: str, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    async def run_prompt(
        self,
        *,
        agent_name: str,
        stage_name: str,
        instruction: str,
        inputs: dict[str, object],
        output_model: type[BaseModel],
    ) -> BaseModel | Mapping[str, object]:
        app_name = "aog_recovery"
        session_service = InMemorySessionService()
        session_id = uuid4().hex
        user_id = agent_name
        agent = LlmAgent(
            name=f"{agent_name}_{stage_name}",
            model=self.model_name,
            instruction=instruction,
            output_schema=output_model,
            timeout=self.timeout_seconds,
            include_contents="none",
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        )
        runner = Runner(
            agent=agent,
            app_name=app_name,
            session_service=session_service,
        )
        await session_service.create_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        user_message = types.Content(
            role="user",
            parts=[types.Part(text=json.dumps(inputs, sort_keys=True, separators=(",", ":")))],
        )

        try:
            async with asyncio.timeout(self.timeout_seconds):
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=user_message,
                ):
                    if not event.is_final_response() or event.content is None:
                        continue
                    response_text = "\n".join(
                        part.text for part in event.content.parts or () if part.text
                    )
                    if not response_text:
                        raise PromptRunnerError("ADK returned an empty structured response")
                    try:
                        validated_output = output_model.model_validate_json(response_text)
                        return validated_output.model_dump(mode="python")
                    except ValidationError as error:
                        raise PromptRunnerError(
                            "ADK response did not match the stage output schema"
                        ) from error
        except TimeoutError as error:
            raise PromptRunnerError("ADK prompt stage timed out") from error
        except PromptRunnerError:
            raise
        except Exception as error:
            raise PromptRunnerError("ADK prompt stage failed") from error

        raise PromptRunnerError("ADK prompt stage ended without a final response")
