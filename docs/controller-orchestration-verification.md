# Controller Orchestration Verification Evidence

## Verification Run

Environment: Windows, Python 3.14.7, pytest 9.1.1. Commands were run from the repository root on 2026-10-21.

| Command | Result |
|---|---|
| `uv run pytest` | 424 passed in 6.81s |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 190 files already formatted |
| `uv run mypy src` | Success, no issues in 62 source files |

Pytest reported two dependency warnings, neither from project code:

- `google.genai.types`: `_UnionGenericAlias` is deprecated and scheduled for removal in Python 3.17.
- `google.adk.features._feature_decorator`: experimental `FeatureName.PLUGGABLE_AUTH` is enabled.

## Synthetic Demonstration

Run `uv run pytest tests/integration/test_controller_workflow.py -q` for the deterministic orchestration demonstration. It uses a synthetic AOG case, fake Maintenance and Materials & Logistics boundaries, and the existing local/mock Operations adapters. It covers a four-candidate unranked handoff, missing ETA, stale and conflicting evidence, a candidate-local specialist failure, an Operations timeout, H3/H4 context append failure, compliance exclusion, invalid intake with no invocation, and a pending human gate.

The suite result at verification time is 5 passed. It includes the route-policy case proving that an omitted Materials & Logistics specialist and an explicitly unavailable source are not invoked and remain visible in handoff state. No live model, network, airline source, or operational write is used. Results are advisory only; no candidate is scored or ranked.

## AI-Assisted Iteration Record

- Strict Pydantic fixtures initially supplied enum values as strings. The contract tests exposed the strict-boundary mismatch; fixtures were changed to use typed enum values.
- Candidate tests exposed the missing failed-part identifier needed for H3/H4. Repair candidates now preserve it as explicit missing data instead of inferring a part number.
- The high-confidence compliance fixture initially received a 0.69 cap because its aircraft ID did not match the deterministic Operations schedule. The fixture was corrected to use the schedule's synthetic aircraft identity; the approval-bypass test then exercised confidence at or above 0.70 while the gate remained pending.
- Recorder and audit integration tests exposed event-order assumptions and patch-placement defects. The assertions were narrowed to distinguish general lifecycle events from H3/H4 request/response records, and the same focused tests were rerun after each correction.
- The orchestration verification identified that recorded routing was not enforced during fan-out. The route is now passed through the workflow, omitted/unavailable specialist calls are suppressed, and route/source-health state is retained in the handoff; the duplicated follow-up task entry was removed and the single task was verified.
- Ruff and mypy findings were corrected before the final repository-wide gates. Full outputs are summarized above.

This is inspectable development evidence, not a human peer review or approval. It does not claim a RAPID recommendation, Go/No-Go decision, or sponsor acceptance.

## Modified-File Inventory

Implementation:

- `src/aog_recovery/controller/__init__.py`
- `src/aog_recovery/controller/adk_agent.py`
- `src/aog_recovery/controller/aggregation.py`
- `src/aog_recovery/controller/candidates.py`
- `src/aog_recovery/controller/compliance.py`
- `src/aog_recovery/controller/context.py`
- `src/aog_recovery/controller/intake.py`
- `src/aog_recovery/controller/models.py`
- `src/aog_recovery/controller/orchestration.py`
- `src/aog_recovery/controller/workflow.py`

Tests:

- `tests/contracts/test_controller_contracts.py`
- `tests/integration/test_controller_compliance.py`
- `tests/integration/test_controller_specialist_fanout.py`
- `tests/integration/test_controller_workflow.py`
- `tests/integration/test_h3_h4_recorder.py`

Documentation and tracking:

- `docs/shared-foundation-contracts.md`
- `docs/shared-foundation-verification.md`
- `docs/controller-orchestration-verification.md`
- `openspec/changes/orchestrate-aog-recovery-cases/tasks.md`
- `openspec/changes/orchestrate-aog-recovery-cases/proposal.md`
- `openspec/changes/orchestrate-aog-recovery-cases/design.md`
- `openspec/changes/orchestrate-aog-recovery-cases/specs/recovery-orchestration/spec.md`

The orchestration proposal, design, capability spec, and task tracker were updated to incorporate the verified route-enforcement behavior. The follow-up `harden-controller-orchestration` remains unchanged per user direction and still contains overlapping route/source-health scope.

## Deferred Work and Human Decisions

This capability stops before weighted scoring, ranking, close-score handling, final recommendation prose, and decision-brief rendering (ARD-CTL-009/011..016/019); those capabilities are deferred to the later `rank-aog-recovery-options` change. Human decision collection remains separate, and every operational and airworthiness decision requires the authorized human roles. No agent executes a booking, purchase, transfer, dispatch, delay, aircraft assignment, or other operational action.

RAPID peer review, Go/No-Go, sponsor delivery and live Q&A, and deployment readiness also remain human/project responsibilities (ARD-TEC-020, ARD-RUB-005..011, ARD-DEP-001 onward). The selected follow-on name is `rank-aog-recovery-options`; that future change does not transfer operational or airworthiness approval away from the authorized people.