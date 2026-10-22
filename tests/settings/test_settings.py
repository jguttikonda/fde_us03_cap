import pytest
from pydantic import SecretStr, ValidationError

from aog_recovery.config import AdapterMode, AogSettings


def test_settings_load_valid_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AOG_ADAPTER_MODE", "local")
    monkeypatch.setenv("AOG_TOOL_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("AOG_AGENT_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("AOG_OPERATIONS_TIMEOUT_SECONDS", "20")
    monkeypatch.setenv("AOG_OPERATIONS_MAX_WORKERS", "3")

    settings = AogSettings(_env_file=None)

    assert settings.adapter_mode is AdapterMode.LOCAL
    assert settings.tool_timeout_seconds == 15
    assert settings.agent_timeout_seconds == 45
    assert settings.operations_timeout_seconds == 20
    assert settings.operations_max_workers == 3


@pytest.mark.parametrize(
    ("setting_name", "value"),
    [
        ("AOG_ADAPTER_MODE", "enterprise"),
        ("AOG_TOOL_TIMEOUT_SECONDS", "0"),
        ("AOG_AGENT_TIMEOUT_SECONDS", "121"),
        ("AOG_OPERATIONS_TIMEOUT_SECONDS", "0"),
        ("AOG_OPERATIONS_MAX_WORKERS", "17"),
        ("AOG_ESCALATION_CONFIDENCE_THRESHOLD", "0.8"),
    ],
)
def test_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch, setting_name: str, value: str
) -> None:
    monkeypatch.setenv(setting_name, value)

    with pytest.raises(ValidationError):
        AogSettings(_env_file=None)


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
