from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import StringConstraints, field_validator

from aog_recovery.contracts.base import ContractModel

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class HumanDecisionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUEST_INFORMATION = "request_information"


class ReviewerRole(StrEnum):
    OPS_LEAD = "ops_lead"
    MAINTENANCE_AIRWORTHINESS = "maintenance_airworthiness"


class HumanDecisionRecord(ContractModel):
    schema_version: Literal["1.0"]
    decision_id: NonEmptyString
    case_id: NonEmptyString
    decision: HumanDecisionType
    selected_action: NonEmptyString | None
    selected_option_id: NonEmptyString | None
    reviewer_id: NonEmptyString
    reviewer_role: ReviewerRole
    decided_at: datetime
    rationale: NonEmptyString
    recommendation_version: NonEmptyString

    @field_validator("decided_at")
    @classmethod
    def require_timezone_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value
