import pytest
from pydantic import SecretStr, ValidationError

from aog_recovery.config import AdapterMode, AogSettings


def test_settings_load_valid_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AOG_ADAPTER_MODE", "local")
    monkeypatch.setenv("AOG_TOOL_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("AOG_AGENT_TIMEOUT_SECONDS", "45")

    settings = AogSettings(_env_file=None)

    assert settings.adapter_mode is AdapterMode.LOCAL
    assert settings.tool_timeout_seconds == 15
    assert settings.agent_timeout_seconds == 45


def test_operations_settings_defaults_are_typed_and_documented() -> None:
    settings = AogSettings(_env_file=None)

    assert settings.operations_source_freshness_seconds == 900
    assert settings.operations_service_level_order == ("priority", "standard")
    assert settings.operations_impact_thresholds.critical_delay_minutes == 300
    assert settings.operations_mock_cost_rates.currency == "USD"
    assert settings.operations_mock_cost_rates.swap_flat_cost is not None


def test_operations_settings_load_service_order_from_json_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AOG_OPERATIONS_SERVICE_LEVEL_ORDER", '["critical","priority","standard"]')

    settings = AogSettings(_env_file=None)

    assert settings.operations_service_level_order == ("critical", "priority", "standard")


@pytest.mark.parametrize(
    ("setting_name", "value"),
    [
        ("AOG_ADAPTER_MODE", "enterprise"),
        ("AOG_TOOL_TIMEOUT_SECONDS", "0"),
        ("AOG_AGENT_TIMEOUT_SECONDS", "121"),
        ("AOG_ESCALATION_CONFIDENCE_THRESHOLD", "0.8"),
        ("AOG_OPERATIONS_SOURCE_FRESHNESS_SECONDS", "0"),
        ("AOG_OPERATIONS_CRITICAL_DELAY_MINUTES", "60"),
        ("AOG_OPERATIONS_SERVICE_LEVEL_ORDER", "[]"),
        ("AOG_OPERATIONS_SERVICE_LEVEL_ORDER", '["priority","priority"]'),
        ("AOG_OPERATIONS_MAX_READ_RETRIES", "4"),
        ("AOG_OPERATIONS_MOCK_SWAP_FLAT_COST", "-1"),
    ],
)
def test_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, setting_name: str, value: str
) -> None:
    monkeypatch.setenv(setting_name, value)

    with pytest.raises(ValidationError):
        AogSettings(_env_file=None)


def test_unset_optional_mock_cost_rate_stays_unavailable() -> None:
    settings = AogSettings(_env_file=None, operations_mock_swap_flat_cost=None)

    assert settings.operations_mock_cost_rates.swap_flat_cost is None


def test_secret_is_not_in_repr_serialization_or_logs(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    synthetic_secret = "synthetic-test-secret-not-real"
    monkeypatch.setenv("AOG_PROVIDER_API_KEY", synthetic_secret)

    settings = AogSettings(_env_file=None)

    assert settings.provider_api_key == SecretStr(synthetic_secret)
    assert synthetic_secret not in repr(settings)
    assert synthetic_secret not in settings.model_dump_json()
    assert synthetic_secret not in caplog.text
