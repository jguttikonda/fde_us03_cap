from typing import Annotated

from pydantic import StringConstraints, model_validator

from aog_recovery.contracts.base import ContractModel

NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ValidationFinding(ContractModel):
    field_path: NonEmptyString
    code: NonEmptyString
    message: NonEmptyString


class ValidationReport(ContractModel):
    is_valid: bool
    findings: tuple[ValidationFinding, ...]

    @model_validator(mode="after")
    def validity_matches_findings(self) -> ValidationReport:
        if self.is_valid != (not self.findings):
            raise ValueError("is_valid must match whether findings are present")
        return self
