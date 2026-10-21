from collections.abc import Collection

from pydantic import BaseModel, ValidationError

from aog_recovery.contracts.agent import AgentResult
from aog_recovery.contracts.case import AogCase
from aog_recovery.validation.models import ValidationFinding, ValidationReport


def _validate_model[Contract: BaseModel](
    model: type[Contract], payload: object
) -> tuple[Contract | None, ValidationReport]:
    try:
        validated = model.model_validate(payload)
    except ValidationError as error:
        findings = tuple(
            sorted(
                (
                    ValidationFinding(
                        field_path=".".join(str(part) for part in issue["loc"]) or "$",
                        code=issue["type"],
                        message=issue["msg"],
                    )
                    for issue in error.errors()
                ),
                key=lambda finding: (finding.field_path, finding.code, finding.message),
            )
        )
        return None, ValidationReport(is_valid=False, findings=findings)
    return validated, ValidationReport(is_valid=True, findings=())


def validate_case(payload: object) -> ValidationReport:
    _, report = _validate_model(AogCase, payload)
    return report


def validate_agent_result(
    payload: object, available_evidence_ids: Collection[str]
) -> ValidationReport:
    result, report = _validate_model(AgentResult, payload)
    if result is None:
        return report

    referenced_ids = set(result.evidence_references)
    for assumption in result.assumptions:
        referenced_ids.update(assumption.evidence_references)

    missing_references = sorted(referenced_ids.difference(available_evidence_ids))
    findings = tuple(
        ValidationFinding(
            field_path=f"evidence_references[{evidence_id}]",
            code="unknown_evidence_reference",
            message=f"evidence reference '{evidence_id}' is not available",
        )
        for evidence_id in missing_references
    )
    if findings:
        return ValidationReport(is_valid=False, findings=findings)
    return report
