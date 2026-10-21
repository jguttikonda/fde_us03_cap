from enum import StrEnum
from typing import Annotated

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdapterMode(StrEnum):
    LOCAL = "local"


class AogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AOG_",
        extra="forbid",
        validate_default=True,
    )

    adapter_mode: AdapterMode = AdapterMode.LOCAL
    tool_timeout_seconds: Annotated[int, Field(ge=1, le=60)] = 10
    agent_timeout_seconds: Annotated[int, Field(ge=1, le=120)] = 30
    preferred_confidence_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.70
    escalation_confidence_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.50
    maintenance_recurrence_threshold: Annotated[int, Field(ge=1, le=100)] = 3
    maintenance_recurrence_window_days: Annotated[int, Field(ge=1, le=3650)] = 90
    materials_stale_confidence_penalty: Annotated[float, Field(ge=0.0, le=1.0)] = 0.10
    provider_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)

    @model_validator(mode="after")
    def require_ordered_confidence_thresholds(self) -> AogSettings:
        if self.escalation_confidence_threshold >= self.preferred_confidence_threshold:
            raise ValueError("escalation threshold must be below preferred threshold")
        return self
