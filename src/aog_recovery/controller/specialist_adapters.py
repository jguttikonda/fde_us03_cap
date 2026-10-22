"""Typed adapters from candidate requests to existing specialist agents."""

import json
from typing import Protocol

from pydantic import ValidationError

from aog_recovery.contracts.agent import AgentResult, AgentResultStatus, AgentRole, StructuredError
from aog_recovery.controller.orchestration import CandidateSpecialistRequest
from aog_recovery.maintenance.models import MaintenanceAssessmentInput
from aog_recovery.materials_logistics.agent import (
    MaterialsLogisticsAssessmentInput,
)


class MaintenanceAgentPort(Protocol):
    async def assess(self, payload: object) -> AgentResult: ...


class MaterialsLogisticsAgentPort(Protocol):
    async def assess(self, payload: object) -> AgentResult: ...


class MaintenanceSpecialistAdapter:
    def __init__(self, agent: MaintenanceAgentPort) -> None:
        self._agent = agent

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        payload = request.candidate.source.maintenance_assessment_input
        if payload is None:
            return _input_failure(AgentRole.MAINTENANCE, "maintenance_input_invalid")
        try:
            assessment_input = MaintenanceAssessmentInput.model_validate_json(json.dumps(payload))
        except TypeError, ValueError, ValidationError:
            return _input_failure(AgentRole.MAINTENANCE, "maintenance_input_invalid")
        if assessment_input.case != request.case:
            return _input_failure(AgentRole.MAINTENANCE, "maintenance_case_mismatch")

        unresolved = _maintenance_evidence_references(assessment_input).difference(
            request.available_evidence_ids
        )
        if unresolved:
            return _input_failure(AgentRole.MAINTENANCE, "maintenance_evidence_unresolved")
        return await self._agent.assess(assessment_input)


class MaterialsLogisticsSpecialistAdapter:
    def __init__(self, agent: MaterialsLogisticsAgentPort) -> None:
        self._agent = agent

    async def assess(self, request: CandidateSpecialistRequest) -> AgentResult:
        payload = request.candidate.source.materials_logistics_assessment_input
        if payload is None:
            return _input_failure(AgentRole.MATERIALS_LOGISTICS, "materials_input_invalid")
        try:
            assessment_input = MaterialsLogisticsAssessmentInput.model_validate_json(
                json.dumps(payload)
            )
        except TypeError, ValueError, ValidationError:
            return _input_failure(AgentRole.MATERIALS_LOGISTICS, "materials_input_invalid")
        if assessment_input.case != request.case:
            return _input_failure(AgentRole.MATERIALS_LOGISTICS, "materials_case_mismatch")

        selected_options = request.candidate.sourcing_options
        if selected_options:
            if len(selected_options) != 1 or selected_options[0] not in (
                assessment_input.assessment.sourcing_options
            ):
                return _input_failure(
                    AgentRole.MATERIALS_LOGISTICS,
                    "materials_sourcing_option_unresolved",
                )
            assessment_input = assessment_input.model_copy(
                update={
                    "assessment": assessment_input.assessment.model_copy(
                        update={"sourcing_options": selected_options}
                    )
                }
            )

        unresolved = _materials_evidence_references(assessment_input).difference(
            request.available_evidence_ids
        )
        if unresolved:
            return _input_failure(AgentRole.MATERIALS_LOGISTICS, "materials_evidence_unresolved")
        return await self._agent.assess(assessment_input)


def _input_failure(role: AgentRole, category: str) -> AgentResult:
    error = StructuredError(
        schema_version="1.0",
        category=category,
        component=f"controller:{role.value}",
        message=f"{role.value} candidate input could not be validated for this request",
        retryable=False,
        case_impact=f"{role.value} candidate analysis is unavailable",
    )
    return AgentResult(
        schema_version="1.0",
        agent_role=role,
        status=AgentResultStatus.FAILED,
        summary=f"{role.value} candidate input validation failed",
        confidence=0.0,
        assumptions=(),
        evidence_references=(),
        role_payload={"error": error.model_dump(mode="json")},
    )


def _maintenance_evidence_references(
    assessment_input: MaintenanceAssessmentInput,
) -> set[str]:
    evidence = [
        *assessment_input.maintenance_history,
        *assessment_input.engineering_constraints,
        *assessment_input.safety_conditions,
    ]
    if assessment_input.aircraft_metadata is not None:
        evidence.append(assessment_input.aircraft_metadata)
    if assessment_input.work_order is not None:
        evidence.append(assessment_input.work_order.evidence)
    references = {item.evidence_id for item in evidence}
    references.update(
        reference
        for reference in (
            assessment_input.need_by_evidence_reference,
            assessment_input.parts_readiness_evidence_reference,
        )
        if reference is not None
    )
    for dependency in assessment_input.part_dependencies:
        references.update(dependency.evidence_references)
    return references


def _materials_evidence_references(
    assessment_input: MaterialsLogisticsAssessmentInput,
) -> set[str]:
    references = set(assessment_input.evidence_summary.evidence_references)
    references.update(
        item.claim_reference for item in assessment_input.assessment.part_availability
    )
    for item in assessment_input.assessment.part_eligibility:
        references.update(item.evidence_references)
    for option in assessment_input.assessment.sourcing_options:
        references.update(option.evidence_references)
    return references
