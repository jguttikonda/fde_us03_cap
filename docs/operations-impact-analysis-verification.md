# Operations Impact Analysis Verification

Change: `implement-operations-impact-analysis`. Raw output: [evidence/operations-verification-run.txt](evidence/operations-verification-run.txt).

## Environment and results

Python 3.14.7, Google ADK 2.12.0, Pydantic 2.14.1, pytest 9.1.1, Ruff 0.17.1, mypy 1.20.2.

| Check | Command | Result |
|---|---|---|
| Full suite (foundation + readiness contract + operations) | `uv run pytest` | 293 passed |
| Operations coverage | `--cov=aog_recovery.operations` | 99% (8 of 886 statements) |
| Lint / format | `uv run ruff check .` / `ruff format --check .` | passed / 165 files formatted |
| Types | `uv run mypy` | no issues in 34 source files |
| OpenSpec | `openspec validate ... --strict` | valid |

Offline demonstration: `uv run python -m aog_recovery.operations.demo [scenario] [--json]`.

## Limits of this evidence

- The reasoning stage in tests and the demonstration is `DeterministicReasoner`, a template, not a language model. The ADK `LlmAgent` is built and its tool is exercised, but no live model was called, so no claim is made about live LLM behavior. Live evaluation needs a separately approved model configuration.
- All data is synthetic. Thresholds, buffers, and cost rates are mock values for owner review.
- `defer_to_controller` extends the proposal's decision list so the agent never ranks options (ARD-SYS-005).
- Peer review, RAPID Go/No-Go, and sponsor communication remain human activities.

## Requirement-to-test traceability

| Requirements | Implementation | Tests (`tests/operations/`) |
|---|---|---|
| ARD-OPS-001/004, ARD-DAT-001/009/010, ARD-GOV-005 | `models.py` request and candidate contracts; missing ETA stays missing data | `test_ops_contracts.py`, `test_ops_rules.py::test_missing_eta_*`, `test_ops_agent.py::test_missing_eta_*` |
| ARD-OPS-002/008 | `rules.py` schedule validation, crew gap, double-booked substitute, time-estimate conflict | `test_ops_rules.py` (boundary 60/61 minutes, resource names, determinism) |
| ARD-OPS-003, ARD-NFR-006 | `apply_disruption_thresholds`, `settings.py` | `test_ops_rules.py` thresholds and uplift; `test_ops_settings.py` |
| ARD-OPS-009, ARD-CTL-019 | `check_load_redistribution`, `compute_cost` | `test_ops_rules.py` case 6 (900 allocated, 300 unprotected), cut-off, priority order, cost sums; `test_ops_agent.py::test_swap_capacity_*` |
| ARD-OPS-009 (own-network and partner flight sourcing) | `find_replacement_flights`, `ReroutePolicy`, `alternate_flights` source, per-option reroute plan | `test_ops_rules.py` (usability reasons, own-first order, service level, route, cost with rerouting); `test_ops_agent.py` (`partner_reroute`, `own_network_only`, cost cap, flight-search outage); `test_ops_contracts.py` |
| ARD-OPS-005/006/007, ARD-GOV-001..005 | `agent.py` confidence policy, status, trade-offs | `test_ops_agent.py` normal, stale, partial, conflicting, low-confidence, no-viable, materiality tests |
| ARD-RES-002..007, ARD-NFR-002 | `gateway.py` bounded same-id retry, structured failures, `SOURCE_UNAVAILABLE` warning | `test_ops_gateway.py`; `test_ops_agent.py::test_package_timeout_*`, `test_essential_schedule_failure_*`, isolation test |
| ARD-SEC-001..005, ARD-TST-007 | allowlist, strict untrusted-data models, facts-only reasoning | `test_ops_security_and_gate.py`, `test_ops_gateway.py` (unknown fields, case mismatch), `test_ops_contracts.py` allowlist |
| ARD-SEC-006..009, ARD-OBS-001..004 | correlated redacted `AuditEvent`s | `test_ops_agent.py::test_audit_events_*`, `test_ops_security_and_gate.py` redaction |
| ARD-PRN-001..004, ARD-GOV-008, ARD-SEC-008, ARD-TST-005 | advisory literals, guardrail, no write surface | `test_ops_reasoning.py`, `test_ops_security_and_gate.py` human-gate tests |
| ARD-TEC-002/005, ARD-TST-009 | `adk_agent.py`, `prompts.py` | `test_ops_adk_and_demo.py`, `test_ops_reasoning.py::test_prompt_stage_outputs_*`, no-network tests |
| ARD-DAT-004 (ETA handoff from Maintenance and M&L) | shared `contracts/readiness.py` (`ReadinessEstimate`, window and lead-time helpers), `CandidateOption.with_readiness` | `tests/contracts/test_readiness_contract.py`; `tests/operations/test_ops_proposal_payload.py` (proposal payload equals the implemented models) |
| ARD-DAT-004, ARD-CTL-006 | evidence ids and ETA references resolve | `test_ops_agent.py::test_result_envelope_passes_shared_validation_*` |

## AI-assisted development notes

The change was developed with GitHub Copilot following the OpenSpec flow (`proposal`, `design`, `specs`, `tasks`, then implementation). Design decisions, the ARD mapping, and all numeric expectations in the tests were checked against the proposal's functional cases by running the code. Human review is required before merge or archive.

## Modified-file inventory for peer review

- Additive shared edits: `src/aog_recovery/contracts/tool.py`, `src/aog_recovery/adapters/local.py` (including the `alternate_flights` tool), `src/aog_recovery/validation/boundaries.py` (`validate_contract` wrapper), `.env.example`; `docs/agent-proposals/operations-agent-proposal.md` (flight-sourcing tool and Flight Capacity API).
- New package: `src/aog_recovery/operations/` (models, settings, rules, gateway, reasoning, prompts, agent, adk_agent, synthetic, demo).
- New tests: `tests/operations/` (8 files, 195 tests).
- OpenSpec: `openspec/changes/implement-operations-impact-analysis/`.
