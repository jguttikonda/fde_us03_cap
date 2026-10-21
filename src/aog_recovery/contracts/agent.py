from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from aog_recovery.contracts.base import ContractModel
from aog_recovery.contracts.evidence import Assumption

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AgentRole(StrEnum):
    CONTROLLER = "controller"
    MAINTENANCE = "maintenance"
    MATERIALS_LOGISTICS = "materials_logistics"
    OPERATIONS = "operations"


class AgentResultStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    ESCALATION_REQUIRED = "escalation_required"
    FAILED = "failed"


class AgentResult(ContractModel):
    schema_version: Literal["1.0"]
    agent_role: AgentRole
    status: AgentResultStatus
    summary: NonEmptyString
    confidence: float = Field(ge=0.0, le=1.0)
    assumptions: tuple[Assumption, ...]
    evidence_references: tuple[NonEmptyString, ...]
    role_payload: dict[str, object]


class StructuredError(ContractModel):
    schema_version: Literal["1.0"]
    category: NonEmptyString
    component: NonEmptyString
    message: NonEmptyString
    retryable: bool
    case_impact: NonEmptyString


class RecoveryOption(ContractModel):
    option_id: NonEmptyString
    description: NonEmptyString
    evidence_references: tuple[NonEmptyString, ...]
    assumptions: tuple[Assumption, ...]
