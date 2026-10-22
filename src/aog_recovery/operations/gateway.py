"""Read-only Operations tool gateway (ARD-SEC-001..004, ARD-RES-002/003/005/006, ARD-NFR-002).

Calls allowlisted read-only adapters as the Operations role, retries only retryable failures a
bounded number of times with the same request identifier, and validates tool data as untrusted
input before anything else uses it. There is deliberately no write method.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ValidationError

from aog_recovery.adapters.protocols import ReadOnlyAdapter
from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity, EvidenceWarning
from aog_recovery.contracts.tool import ToolName, ToolRequest, ToolResult, ToolResultStatus
from aog_recovery.operations.models import OperationsRequest
from aog_recovery.operations.settings import OperationsSettings

COMPONENT = "operations-gateway"


class SourceStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class SourceOutcome[T: BaseModel]:
    tool_name: ToolName
    status: SourceStatus
    data: T | None
    evidence: Evidence | None
    warnings: tuple[EvidenceWarning, ...]
    error: StructuredError | None
    attempts: int


class SourceView(Protocol):
    """Read-only view of any SourceOutcome regardless of its data model."""

    @property
    def tool_name(self) -> ToolName: ...
    @property
    def status(self) -> SourceStatus: ...
    @property
    def evidence(self) -> Evidence | None: ...
    @property
    def warnings(self) -> tuple[EvidenceWarning, ...]: ...
    @property
    def error(self) -> StructuredError | None: ...
    @property
    def attempts(self) -> int: ...


def _failure[T: BaseModel](
    tool_name: ToolName, category: str, message: str, attempts: int
) -> SourceOutcome[T]:
    return SourceOutcome(
        tool_name=tool_name,
        status=SourceStatus.FAILED,
        data=None,
        evidence=None,
        warnings=(),
        error=StructuredError(
            schema_version="1.0",
            category=category,
            component=f"{COMPONENT}:{tool_name.value}",
            message=message,
            retryable=False,
            case_impact=f"{tool_name.value} analysis is unavailable for this case",
        ),
        attempts=attempts,
    )


class OperationsToolGateway:
    def __init__(
        self, adapters: Mapping[ToolName, ReadOnlyAdapter], settings: OperationsSettings
    ) -> None:
        self._adapters = dict(adapters)
        self._settings = settings

    def fetch[T: BaseModel](
        self, request: OperationsRequest, tool_name: ToolName, model: type[T]
    ) -> SourceOutcome[T]:
        adapter = self._adapters.get(tool_name)
        if adapter is None:
            return _failure(
                tool_name, "tool_not_configured", "no adapter is configured for this tool", 0
            )

        tool_request = ToolRequest(
            schema_version="1.0",
            request_id=f"{request.request_id}:{tool_name.value}",
            case_id=request.case.case_id,
            trace_context=request.case.trace_context,
            tool_name=tool_name,
            requested_at=request.evaluated_at,
            parameters={
                "aircraft_id": request.case.aircraft_id,
                "affected_flight_numbers": list(request.affected_flight_numbers),
            },
            access_mode="read",
        )

        first_error: StructuredError | None = None
        attempts = 0
        while True:
            attempts += 1
            result = adapter.read(tool_request, AgentRole.OPERATIONS)
            if result.status is not ToolResultStatus.FAILED:
                break
            first_error = first_error or result.error
            retryable = result.error is not None and result.error.retryable
            if not retryable or attempts > self._settings.max_retries:
                break

        if result.case_id != request.case.case_id:
            return _failure(
                tool_name, "case_mismatch", "tool result belongs to a different case", attempts
            )
        if result.status is ToolResultStatus.FAILED:
            return SourceOutcome(
                tool_name=tool_name,
                status=SourceStatus.FAILED,
                data=None,
                evidence=None,
                warnings=(),
                error=first_error,
                attempts=attempts,
            )
        return self._accept(request, tool_name, model, result, attempts)

    def _accept[T: BaseModel](
        self,
        request: OperationsRequest,
        tool_name: ToolName,
        model: type[T],
        result: ToolResult,
        attempts: int,
    ) -> SourceOutcome[T]:
        try:
            data = model.model_validate(result.data)
        except ValidationError:
            return _failure(
                tool_name,
                "malformed_response",
                "source returned data that failed validation",
                attempts,
            )

        claim = f"operations:{tool_name.value}"
        warnings = list(result.warnings)
        codes = {warning.code for warning in warnings}

        max_age = timedelta(minutes=self._settings.evidence_max_age_minutes)
        if request.evaluated_at - result.completed_at > max_age and "STALE_EVIDENCE" not in codes:
            warnings.append(
                EvidenceWarning(
                    warning_id=f"warning-{request.request_id}-{tool_name.value}-age",
                    claim_reference=claim,
                    code="STALE_EVIDENCE",
                    message=(
                        f"source data is older than {self._settings.evidence_max_age_minutes} "
                        "minutes at evaluation time"
                    ),
                    source_reference=result.source,
                )
            )
            codes.add("STALE_EVIDENCE")
        if attempts > 1:
            warnings.append(
                EvidenceWarning(
                    warning_id=f"warning-{request.request_id}-{tool_name.value}-retry",
                    claim_reference=claim,
                    code="RETRIED_AFTER_FAILURE",
                    message=f"source succeeded after {attempts} attempts with the same request id",
                    source_reference=result.source,
                )
            )

        if "CONFLICTING_DATA" in codes:
            validity = EvidenceValidity.CONFLICTING
        elif "STALE_EVIDENCE" in codes:
            validity = EvidenceValidity.STALE
        elif "PARTIAL_DATA" in codes:
            validity = EvidenceValidity.PARTIAL
        else:
            validity = EvidenceValidity.CURRENT

        evidence = Evidence(
            evidence_id=f"evidence-{request.request_id}-{tool_name.value}",
            source=result.source,
            retrieved_at=result.completed_at,
            validity_state=validity,
            claim_reference=claim,
            content={name: len(value) for name, value in data if isinstance(value, tuple)},
        )
        degraded = validity is not EvidenceValidity.CURRENT
        return SourceOutcome(
            tool_name=tool_name,
            status=SourceStatus.DEGRADED if degraded else SourceStatus.OK,
            data=data,
            evidence=evidence,
            warnings=tuple(warnings),
            error=None,
            attempts=attempts,
        )
