# Maintenance & Materials Implementation Evidence

## Verification

Final repository checks, run with Python 3.14.7, pytest 9.1.1, Ruff 0.17.1, and mypy 1.20.2:

| Command | Result |
|---|---|
| `uv run pytest` | 164 passed in 3.65s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 131 files already formatted |
| `uv run mypy src` | Success; no issues found in 40 source files |
| `openspec validate implement-maintenance-materials-logistics-analysis --strict --json` | Valid; no issues |

Pytest reported two dependency warnings: a `google.genai` deprecated internal alias and Google ADK's experimental pluggable-auth feature warning. No project test failed.

## Synthetic Demonstration

Reproduce the integrated scenario with:

```powershell
uv run pytest tests/integration/test_specialist_workflow.py -q
```

The fixed case records three source-backed P-110 failures within 90 days and an engineering-supported P-120 preference. Maintenance runs its three fake ADK stages and supplies repair duration, need-by, and evidence references. Materials & Logistics runs its three fake ADK stages over synthetic inventory, eligibility, and quote evidence. P-110 has no stock; P-120 has four units locally with a minimum threshold of one, verified compatibility/authorization/traceability, a one-hour ETA, and a mock USD 20 quote. The H3/H4 request and response are appended in order and emit case-, trace-, and exchange-correlated audit events.

The degraded variant marks P-120 evidence stale, lowers confidence to 0.72, and preserves the warning through the Materials result and H4. Neither scenario invokes an approval or operational action; approval, ranking, and the final recovery decision remain outside both specialist agents.

The source-to-test maps are retained in [maintenance-test-traceability.md](maintenance-test-traceability.md) and [materials-logistics-test-traceability.md](materials-logistics-test-traceability.md).

## Changed-File Inventory

- OpenSpec change: `proposal.md`, `design.md`, `tasks.md`, and the `maintenance-assessment/spec.md`, `materials-logistics-sourcing/spec.md`, and `maintenance-materials-logistics-coordination/spec.md` deltas under `openspec/changes/implement-maintenance-materials-logistics-analysis/`.
- Runtime setup and shared contracts: `pyproject.toml`, `uv.lock`, `envsetuprequirements.txt`, `src/aog_recovery/config.py`, `src/aog_recovery/adk/prompt_runner.py`, and `docs/shared-foundation-contracts.md`.
- Maintenance package: `src/aog_recovery/maintenance/__init__.py`, `agent.py`, `failure_history.py`, `models.py`, and `validation.py`.
- Materials & Logistics package: `src/aog_recovery/materials_logistics/__init__.py`, `agent.py`, `availability.py`, `degradation.py`, `models.py`, `sourcing.py`, and `tools.py`.
- Coordination package: `src/aog_recovery/coordination/__init__.py`, `models.py`, `recording.py`, and `workflow.py`.
- Focused adapter tests: `tests/adapters/test_materials_agent.py`, `test_materials_availability.py`, `test_materials_degradation.py`, `test_materials_sourcing.py`, and `test_materials_tools.py`.
- Focused contract tests: `tests/contracts/test_materials_logistics.py` and `test_specialist_payloads.py`.
- Focused integration tests: `tests/integration/test_h3_h4_contracts.py`, `test_h3_h4_recorder.py`, `test_h3_h4_workflow.py`, and `test_specialist_workflow.py`.
- Maintenance tests: `tests/maintenance/test_agent_pipeline.py`, `test_failure_history.py`, and `test_input_validation.py`.
- Retained evidence: this file and the two requirement-to-test maps in `docs/`.

## AI-Assisted Iteration Record

- A plan review found the proposal promised two ADK specialists, but the tracked tasks did not include a Materials & Logistics agent. The user approved adding a design decision and task 3.6 before implementation; strict OpenSpec validation then passed.
- A synthetic integration test showed that known, source-backed P-110 unavailability was incorrectly being treated as evidence degradation. The rule was narrowed so only missing, unknown, stale, partial, or conflicting findings make H4 partial; known unavailability remains a complete analysis.
- A separate integration check showed failed-part inventory does not require alternate-part eligibility evidence. Eligibility gates were restricted to alternate/substitute candidates and covered by a regression test.
- Full mypy found the shared ADK prompt boundary declared a Pydantic model return while returning a Python-mode mapping. Pylance references confirmed both specialist adapters were its only callers; the protocol and both adapters now declare the actual `BaseModel | Mapping` result.
- Strict Pydantic fixture and JSON-mode boundary failures were corrected with enum-valued fixtures and `model_validate_json` at the shared `AgentResult` handoff. The full test and static-check results above were rerun after these corrections.

## Agent Contract Audit

The Maintenance and Materials & Logistics proposals agree on the H3 request / H4 response direction, peer roles, and Controller-owned recording boundary; no handshake mismatch was found. The Materials & Logistics proposal has a repeated section 13 heading for validation and output evaluation and ends at section 16 without the template's section 17. The proposal was left unchanged in this implementation; this documentation finding remains for proposal-owner review.

## Human Review Still Required

This evidence is not a substitute for peer review, RAPID sign-off, Go/No-Go, sponsor demonstration/Q&A, or authorized operational and airworthiness approval. None of those approvals or delivery activities is claimed as complete.