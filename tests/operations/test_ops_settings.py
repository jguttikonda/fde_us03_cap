import pytest
from pydantic import ValidationError

from aog_recovery.operations.settings import OperationsSettings


def test_defaults_are_documented_and_ordered() -> None:
    settings = OperationsSettings()
    assert (
        settings.delay_medium_minutes,
        settings.delay_high_minutes,
        settings.delay_critical_minutes,
    ) == (60, 180, 360)
    assert settings.max_retries == 1
    assert settings.base_confidence == 0.90
    assert settings.provisional_confidence_cap == 0.69


def test_environment_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AOG_OPS_DELAY_MEDIUM_MINUTES", "30")
    monkeypatch.setenv("AOG_OPS_SWAP_COST_USD", "1000")
    settings = OperationsSettings()
    assert settings.delay_medium_minutes == 30
    assert settings.swap_cost_usd == 1000


def test_adk_model_reads_shared_env_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADK_MODEL", "model-from-env")
    assert OperationsSettings().adk_model == "model-from-env"


@pytest.mark.parametrize(
    "overrides",
    [
        {"delay_medium_minutes": 200},
        {"delay_high_minutes": 60},
        {"delay_critical_minutes": 180},
        {"provisional_confidence_cap": 0.70},
        {"max_retries": 4},
        {"evidence_max_age_minutes": 0},
        {"penalty_conflict": 1.5},
        {"delay_cost_per_minute_usd": -1},
    ],
)
def test_invalid_settings_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        OperationsSettings(**overrides)  # type: ignore[arg-type]


def test_settings_are_immutable() -> None:
    with pytest.raises(ValidationError):
        OperationsSettings().swap_cost_usd = 0  # type: ignore[misc]
