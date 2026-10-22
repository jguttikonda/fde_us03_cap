"""Controller intake validation and isolated case context (ARD-CTL-001..005)."""

from enum import StrEnum

from aog_recovery.contracts.agent import AgentRole
from aog_recovery.contracts.audit import AuditEvent
from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.case import TraceContext
from aog_recovery.controller.models import ControllerIntake
from aog_recovery.observability.context import correlation_scope
from aog_recovery.observability.structured import emit_event
from aog_recovery.validation.boundaries import validate_contract_json
from aog_recovery.validation.models import ValidationFinding


class IntakeStatus(StrEnum):
    READY = "ready"
    REJECTED = "rejected"


class IntakeValidation(ContractModel):
    status: IntakeStatus
    intake: ControllerIntake | None
    findings: tuple[ValidationFinding, ...]


class RoutingDecision(ContractModel):
    agent_role: AgentRole
    selected: bool
    reason: str


class ControllerCaseContext(ContractModel):
    case_id: str
    request_id: str
    trace_context: TraceContext
    routing_decisions: tuple[RoutingDecision, ...]
    audit_events: tuple[AuditEvent, ...]


class InMemoryCaseContextStore:
    """Process-local case map; each case owns its context and audit trail."""

    def __init__(self) -> None:
        self._cases: dict[str, ControllerCaseContext] = {}

    def start_case(self, intake: ControllerIntake) -> ControllerCaseContext:
        case_id = intake.case.case_id
        if case_id in self._cases:
            raise ValueError(f"case '{case_id}' is already active")

        decisions = (
            RoutingDecision(
                agent_role=AgentRole.MAINTENANCE,
                selected=True,
                reason="Assess repairability, maintenance history, and readiness.",
            ),
            RoutingDecision(
                agent_role=AgentRole.MATERIALS_LOGISTICS,
                selected=True,
                reason="Assess required-part availability, eligibility, and sourcing.",
            ),
            RoutingDecision(
                agent_role=AgentRole.OPERATIONS,
                selected=True,
                reason="Assess flight, fleet, and package impact for candidate options.",
            ),
        )
        event = AuditEvent(
            schema_version="1.0",
            occurred_at=intake.evaluated_at,
            event_type="controller.intake.accepted",
            case_id=case_id,
            request_id=intake.request_id,
            trace_context=intake.case.trace_context,
            component="controller",
            status="accepted",
            evidence_references=(),
            rationale="Validated case intake and recorded specialist routing.",
            details={
                "selected_agents": [decision.agent_role.value for decision in decisions],
            },
        )
        context = ControllerCaseContext(
            case_id=case_id,
            request_id=intake.request_id,
            trace_context=intake.case.trace_context,
            routing_decisions=decisions,
            audit_events=(event,),
        )
        with correlation_scope(case_id, intake.case.trace_context, intake.request_id):
            emit_event(event)
        self._cases[case_id] = context
        return context

    def get_case(self, case_id: str) -> ControllerCaseContext | None:
        return self._cases.get(case_id)


def validate_controller_intake(payload: object) -> IntakeValidation:
    intake, report = validate_contract_json(ControllerIntake, payload)
    if intake is None:
        return IntakeValidation(
            status=IntakeStatus.REJECTED,
            intake=None,
            findings=report.findings,
        )
    return IntakeValidation(status=IntakeStatus.READY, intake=intake, findings=())
