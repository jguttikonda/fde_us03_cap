import json
import logging
from collections.abc import Mapping
from typing import Protocol

from aog_recovery.contracts.audit import AuditEvent

LOGGER = logging.getLogger("aog_recovery")
REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "credential",
    "apikey",
    "authorization",
    "ssn",
    "email",
    "phone",
    "passport",
    "privatechainofthought",
    "chainofthought",
    "privatereasoning",
)


class AppendOnlyAuditSink(Protocol):
    def append(self, record: str) -> None: ...


def _is_sensitive_key(key: str) -> bool:
    normalized = "".join(character for character in key.casefold() if character.isalnum())
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def _redact(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _is_sensitive_key(str(key)) else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    return value


def serialize_event(event: AuditEvent) -> str:
    safe_event = _redact(event.model_dump(mode="json"))
    return json.dumps(safe_event, sort_keys=True, separators=(",", ":"))


def emit_event(event: AuditEvent) -> None:
    LOGGER.info("%s", serialize_event(event))


def append_event(sink: AppendOnlyAuditSink, event: AuditEvent) -> None:
    sink.append(serialize_event(event))
