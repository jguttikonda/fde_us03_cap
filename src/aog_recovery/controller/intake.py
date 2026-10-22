"""Deterministic Controller intake validation and specialist routing (ARD-CTL-001..004)."""

from datetime import datetime

from pydantic import field_validator, model_validator

from aog_recovery.contracts.agent import AgentRole, StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.contracts.evidence import Evidence, EvidenceValidity
from aog_recovery.controller.context import ControllerAuditRecorder
from aog_recovery.controller.models import (
    ControllerIntake,
    RoutingDecision,
    RoutingOmission,
    SourceHealthRecord,
    SourceHealthStatus,
)
from aog_recovery.validation.boundaries import validate_contract_json
from aog_recovery.validation.models import ValidationReport

_SPECIALIST_ROLES = (
    AgentRole.MAINTENANCE,
    AgentRole.MATERIALS_LOGISTICS,
    AgentRole.OPERATIONS,
)


class IntakeRoutingResult(ContractModel):
    """Validation and routing outcome; invalid payloads cannot carry a route."""

    validated_at: datetime
    validation: ValidationReport
    intake: ControllerIntake | None
    routing: RoutingDecision | None
    audit_errors: tuple[StructuredError, ...] = ()

    @field_validator("validated_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_route_only_for_valid_intake(self) -> IntakeRoutingResult:
        if self.validation.is_valid != (self.intake is not None and self.routing is not None):
            raise ValueError("valid intake must have both validated input and routing")
        if self.routing is not None and self.intake is not None:
            if self.routing.case_id != self.intake.case.case_id:
                raise ValueError("routing case_id must match the validated case")
        return self


def prepare_intake(
    payload: object,
    *,
    validated_at: datetime,
    omitted_specialists: tuple[RoutingOmission, ...] = (),
    audit_recorder: ControllerAuditRecorder | None = None,
) -> IntakeRoutingResult:
    """Validate the wire payload, then create an explicit route without invoking agents."""
    intake, report = validate_contract_json(ControllerIntake, payload)
    if intake is None:
        audit_errors: tuple[StructuredError, ...] = ()
        identity = _audit_identity(payload)
        if audit_recorder is not None and identity is not None:
            case_id, trace_context = identity
            error = audit_recorder.record(
                event_id=f"{case_id}:intake-rejected",
                event_type="controller_intake_validation",
                case_id=case_id,
                request_id=f"{case_id}:intake",
                trace_context=trace_context,
                occurred_at=validated_at,
                status="rejected",
                rationale="Intake validation rejected the supplied payload",
                details={
                    "finding_count": len(report.findings),
                    "finding_paths": [finding.field_path for finding in report.findings],
                },
            )
            if error is not None:
                audit_errors = (error,)
        return IntakeRoutingResult(
            validated_at=validated_at,
            validation=report,
            intake=None,
            routing=None,
            audit_errors=audit_errors,
        )

    audit_errors_list: list[StructuredError] = []
    if audit_recorder is not None:
        error = audit_recorder.record(
            event_id=f"{intake.case.case_id}:intake-validated",
            event_type="controller_intake_validation",
            case_id=intake.case.case_id,
            request_id=f"{intake.case.case_id}:intake",
            trace_context=intake.case.trace_context,
            occurred_at=validated_at,
            status="accepted",
            rationale="Versioned case intake passed deterministic validation",
            evidence_references=tuple(item.evidence_id for item in intake.evidence),
            details={"schema_version": intake.schema_version},
        )
        if error is not None:
            audit_errors_list.append(error)

    source_health = _source_health(intake, validated_at)
    omissions_by_role = {item.agent_role: item for item in omitted_specialists}
    routing = RoutingDecision(
        schema_version="1.0",
        case_id=intake.case.case_id,
        selected_roles=tuple(role for role in _SPECIALIST_ROLES if role not in omissions_by_role),
        omitted_roles=tuple(
            omissions_by_role[role] for role in _SPECIALIST_ROLES if role in omissions_by_role
        ),
        source_health=source_health,
        rationale=tuple(
            f"{role.value} selected by deterministic AOG routing policy"
            for role in _SPECIALIST_ROLES
            if role not in omissions_by_role
        )
        + tuple(
            f"{role.value} omitted: {omissions_by_role[role].reason}"
            for role in _SPECIALIST_ROLES
            if role in omissions_by_role
        ),
    )
    if audit_recorder is not None:
        error = audit_recorder.record(
            event_id=f"{intake.case.case_id}:routing",
            event_type="controller_routing",
            case_id=intake.case.case_id,
            request_id=f"{intake.case.case_id}:routing",
            trace_context=intake.case.trace_context,
            occurred_at=validated_at,
            status="selected",
            rationale="Deterministic specialist routing decision recorded",
            evidence_references=tuple(
                reference
                for record in routing.source_health
                for reference in record.evidence_references
            ),
            details={
                "selected_roles": [role.value for role in routing.selected_roles],
                "omitted_roles": [
                    {"role": item.agent_role.value, "reason": item.reason}
                    for item in routing.omitted_roles
                ],
                "source_health_count": len(routing.source_health),
            },
        )
        if error is not None:
            audit_errors_list.append(error)
    return IntakeRoutingResult(
        validated_at=validated_at,
        validation=report,
        intake=intake,
        routing=routing,
        audit_errors=tuple(audit_errors_list),
    )


def _audit_identity(payload: object) -> tuple[str, TraceContext] | None:
    if not isinstance(payload, dict):
        return None
    case = payload.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("case_id"), str):
        return None
    raw_trace = case.get("trace_context")
    if not isinstance(raw_trace, dict):
        return None
    trace_context, report = validate_contract_json(
        TraceContext,
        {
            "trace_id": raw_trace.get("trace_id"),
            "correlation_id": raw_trace.get("correlation_id"),
        },
    )
    if trace_context is None or not report.is_valid:
        return None
    case_id = case["case_id"].strip()
    if not case_id:
        return None
    return case_id, trace_context


def _source_health(
    intake: ControllerIntake,
    checked_at: datetime,
) -> tuple[SourceHealthRecord, ...]:
    records = list(intake.source_health)
    observed_keys = {(item.source_id, item.agent_role) for item in records}
    evidence_by_source: dict[str, list[Evidence]] = {}
    for item in intake.evidence:
        evidence_by_source.setdefault(item.source, []).append(item)

    for source_id, source_evidence in sorted(evidence_by_source.items()):
        if (source_id, None) in observed_keys:
            continue
        status = _evidence_source_status(source_evidence)
        records.append(
            SourceHealthRecord(
                source_id=source_id,
                status=status,
                checked_at=checked_at,
                evidence_references=tuple(sorted(item.evidence_id for item in source_evidence)),
                reason=(
                    None
                    if status is SourceHealthStatus.AVAILABLE
                    else f"Evidence validity indicates {status.value} source data"
                ),
            )
        )

    known_roles = {item.agent_role for item in records if item.agent_role is not None}
    records.extend(
        SourceHealthRecord(
            source_id=f"specialist:{role.value}",
            agent_role=role,
            status=SourceHealthStatus.UNKNOWN,
            checked_at=checked_at,
            evidence_references=(),
            reason="No specialist source-health observation was supplied",
        )
        for role in _SPECIALIST_ROLES
        if role not in known_roles
    )
    return tuple(
        sorted(
            records,
            key=lambda item: (item.source_id, item.agent_role.value if item.agent_role else ""),
        )
    )


def _evidence_source_status(evidence: list[Evidence]) -> SourceHealthStatus:
    states = {item.validity_state for item in evidence}
    if EvidenceValidity.CONFLICTING in states:
        return SourceHealthStatus.CONFLICTING
    if EvidenceValidity.STALE in states:
        return SourceHealthStatus.STALE
    if EvidenceValidity.PARTIAL in states:
        return SourceHealthStatus.PARTIAL
    return SourceHealthStatus.AVAILABLE
