"""Controller-owned end-to-end case workflow (ARD-CTL-001..008/017..018)."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from aog_recovery.config import AogSettings
from aog_recovery.contracts.agent import StructuredError
from aog_recovery.contracts.base import ContractModel
from aog_recovery.controller.candidates import build_candidates
from aog_recovery.controller.compliance import build_unranked_handoff
from aog_recovery.controller.context import (
    ControllerAuditRecorder,
    ControllerCaseContextRecorder,
)
from aog_recovery.controller.intake import IntakeRoutingResult, prepare_intake
from aog_recovery.controller.models import (
    RecoveryDecisionBrief,
    RoutingOmission,
    UnrankedHandoff,
    WorkflowStatus,
)
from aog_recovery.controller.orchestration import (
    OperationsAssessmentPort,
    SpecialistAssessmentPort,
    assess_candidate_specialists,
    assess_operations_candidates,
)
from aog_recovery.controller.recommendation import build_recommendation


class ControllerWorkflowResult(ContractModel):
    """Inspectable validation/routing, unranked handoff, and optional decision brief."""

    intake: IntakeRoutingResult
    handoff: UnrankedHandoff | None
    errors: tuple[StructuredError, ...]
    recommendation: RecoveryDecisionBrief | None = None


class ControllerWorkflow:
    """Deterministically compose typed specialist and Operations boundaries."""

    def __init__(
        self,
        maintenance: SpecialistAssessmentPort,
        materials_logistics: SpecialistAssessmentPort,
        operations: OperationsAssessmentPort,
        recorder: ControllerCaseContextRecorder,
        *,
        settings: AogSettings | None = None,
        audit_recorder: ControllerAuditRecorder | None = None,
        omitted_specialists: tuple[RoutingOmission, ...] = (),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._maintenance = maintenance
        self._materials_logistics = materials_logistics
        self._operations = operations
        self._recorder = recorder
        self._settings = settings or AogSettings()
        self._audit_recorder = audit_recorder or getattr(recorder, "audit", None)
        self._omitted_specialists = omitted_specialists
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(self, payload: object) -> ControllerWorkflowResult:
        intake_result = prepare_intake(
            payload,
            validated_at=self._clock(),
            omitted_specialists=self._omitted_specialists,
            audit_recorder=self._audit_recorder,
        )
        if (
            intake_result.intake is None
            or intake_result.routing is None
            or intake_result.audit_errors
        ):
            return ControllerWorkflowResult(
                intake=intake_result,
                handoff=None,
                errors=intake_result.audit_errors,
            )

        candidates = build_candidates(intake_result.intake)
        specialist_results = await assess_candidate_specialists(
            intake_result.intake,
            candidates,
            self._maintenance,
            self._materials_logistics,
            self._recorder,
            routing=intake_result.routing,
            settings=self._settings,
            clock=self._clock,
            audit_recorder=self._audit_recorder,
        )
        operations_results = await assess_operations_candidates(
            intake_result.intake,
            specialist_results,
            self._operations,
            clock=self._clock,
            audit_recorder=self._audit_recorder,
        )
        handoff = build_unranked_handoff(
            intake_result.intake.case,
            operations_results,
            routing=intake_result.routing,
            audit_recorder=self._audit_recorder,
            occurred_at=self._clock(),
        )
        audit_failure = any(
            error.category == "controller_audit_append_failed" for error in handoff.errors
        )
        recommendation = (
            None
            if audit_failure or handoff.status is WorkflowStatus.FAILED
            else build_recommendation(
                handoff,
                audit_recorder=self._audit_recorder,
                occurred_at=self._clock(),
            )
        )
        report_errors = recommendation.errors if recommendation is not None else ()
        return ControllerWorkflowResult(
            intake=intake_result,
            handoff=handoff,
            errors=(*handoff.errors, *report_errors),
            recommendation=recommendation,
        )


class ControllerWorkflowPort(Protocol):
    async def run(self, payload: object) -> ControllerWorkflowResult: ...
