from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from aog_recovery.operations.assessment import NonNegativeMoney, OptionCostRates
from aog_recovery.operations.contracts import CurrencyCode, NonEmptyString
from aog_recovery.operations.validation import ImpactThresholds


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
    operations_timeout_seconds: Annotated[int, Field(ge=1, le=120)] = 30
    operations_max_workers: Annotated[int, Field(ge=1, le=16)] = 2
    preferred_confidence_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.70
    escalation_confidence_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.50
    operations_source_freshness_seconds: Annotated[int, Field(ge=1, le=86_400)] = 900
    operations_medium_delay_minutes: Annotated[int, Field(gt=0)] = 30
    operations_high_delay_minutes: Annotated[int, Field(gt=0)] = 120
    operations_critical_delay_minutes: Annotated[int, Field(gt=0)] = 300
    operations_service_level_order: tuple[NonEmptyString, ...] = ("priority", "standard")
    operations_max_read_retries: Annotated[int, Field(ge=0, le=3)] = 1
    operations_confidence_degradation_per_issue: Annotated[float, Field(ge=0.0, le=1.0)] = 0.10
    operations_mock_cost_currency: CurrencyCode = "USD"
    operations_mock_delay_cost_per_minute: NonNegativeMoney | None = Decimal("1.00")
    operations_mock_swap_flat_cost: NonNegativeMoney | None = Decimal("500.00")
    operations_mock_unprotected_package_exposure: NonNegativeMoney | None = Decimal("2.00")
    provider_api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)

    @model_validator(mode="after")
    def validate_settings(self) -> AogSettings:
        if self.escalation_confidence_threshold >= self.preferred_confidence_threshold:
            raise ValueError("escalation threshold must be below preferred threshold")
        if not (
            self.operations_medium_delay_minutes
            < self.operations_high_delay_minutes
            < self.operations_critical_delay_minutes
        ):
            raise ValueError("Operations impact thresholds must be strictly increasing")
        if not self.operations_service_level_order:
            raise ValueError("Operations service-level order must not be empty")
        if len(set(self.operations_service_level_order)) != len(
            self.operations_service_level_order
        ):
            raise ValueError("Operations service-level order must not contain duplicates")
        return self

    @property
    def operations_impact_thresholds(self) -> ImpactThresholds:
        return ImpactThresholds(
            medium_delay_minutes=self.operations_medium_delay_minutes,
            high_delay_minutes=self.operations_high_delay_minutes,
            critical_delay_minutes=self.operations_critical_delay_minutes,
        )

    @property
    def operations_mock_cost_rates(self) -> OptionCostRates:
        return OptionCostRates(
            currency=self.operations_mock_cost_currency,
            delay_per_minute=self.operations_mock_delay_cost_per_minute,
            swap_flat_cost=self.operations_mock_swap_flat_cost,
            unprotected_package_exposure=self.operations_mock_unprotected_package_exposure,
        )
