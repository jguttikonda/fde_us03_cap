# Proposal

## Why

The AOG Recovery Coordinator has approved architecture and agent contracts, but no shared implementation foundation yet. Establishing consistent typed case, evidence, agent, and tool contracts with deterministic validation and traceability before specialist reasoning is built will reduce integration risk and make degraded data and approval boundaries testable from the start.

## What Changes

- Define a Python project structure using Google ADK for runtime agent, tool, and session abstractions, with separate packages for shared contracts, deterministic validation, typed adapters, configuration, observability, and test fixtures.
- Define versioned Pydantic 2 models for AOG cases, agent result envelopes, evidence and confidence, structured errors, tool requests/results, correlation identifiers, audit events, and human approval records.
- Specify deterministic validation for required intake, evidence provenance/freshness, schema/version compatibility, explicit unknowns and conflicts, and confidence-to-escalation thresholds.
- Establish read-only local/mock adapter contracts and representative deterministic fixtures for enterprise-system boundaries; document, but do not implement, extension points for later live integrations.
- Define typed `pydantic-settings` configuration, bounded timeout defaults, structured/redacted logging, and case/trace/correlation propagation.
- Provide reusable pytest fixtures and contract/scenario tests for valid and invalid inputs, partial/stale/conflicting evidence, adapter failures, trace propagation, and approval gating.
- Preserve advisory-only operation: the foundation can validate, report, and record human decisions, but cannot perform operational actions or treat a recommendation as approval.
- Defer all specialist agent reasoning, live enterprise integrations, and operational write capabilities.

## Capabilities

### New Capabilities

- `shared-foundation`: Versioned shared contracts and deterministic runtime boundaries for AOG cases, evidence, agent/tool results, configuration, observability, adapters, and human approval.

### Modified Capabilities

- None. The repository has no existing OpenSpec capability specifications.

## Impact

- Adds the initial Python package layout, `pyproject.toml` dependency/configuration declarations, shared Pydantic models, validators, adapter interfaces and local/mock implementations, logging/correlation utilities, and reusable pytest fixtures/tests.
- Uses the approved Python, Google ADK, Pydantic 2, `pydantic-settings`, pytest, and Ruff stack. Version compatibility must be checked before implementation (ARD-TEC-013); no web framework, database, broker, vector store, container platform, or second agent framework is introduced.
- Does not call live airline systems or add APIs that execute operational actions. Future live adapters must preserve the typed, read-only contracts and controls specified here.

## ARD Traceability

### Addressed

- **ARD-TEC-001..005, ARD-TEC-008..014** — specify Python, ADK, Pydantic, typed settings, governed model access boundary, pytest/Ruff, declared dependencies, framework minimization, compatible versions, and reproducible setup.
- **ARD-SYS-007..009** — isolate enterprise access behind typed adapters, require deterministic local/mock implementations, and define compatible future integration seams.
- **ARD-DAT-001..010, ARD-DAT-012** — define versioned case, evidence, agent, tool, failure, and recovery-option contracts with explicit provenance, unknowns, and correlation.
- **ARD-CTL-001..003, ARD-CTL-005..008** — establish intake validation, source-health representation, case isolation, and typed validation of incomplete or contradictory results; Controller workflow execution itself is deferred.
- **ARD-GOV-001..008, ARD-SEC-001..009** — encode confidence thresholds, explicit human decisions and approval records, read-only defaults, allowlists, untrusted-input validation, secret/sensitive-data controls, safety-claim limits, and append-oriented audit expectations.
- **ARD-RES-001..007, ARD-OBS-001..004, ARD-NFR-001..007** — define visible structured failures/degraded results, bounded timeouts and retries, case/trace identifiers, structured audit events, reproducibility, module boundaries, configuration, and dependency declarations.
- **ARD-TST-001..003, ARD-TST-005, ARD-RUB-001..004** — define contract, invalid-input, failure, partial-evidence, confidence, and no-approval-bypass verification, with requirement-to-test traceability.

### Deferred

- **ARD-TEC-006..007, ARD-TEC-017..020** — MCP is conditional on crossing a process/service boundary; async execution, CI, security scanning, retained capstone evidence, and human review processes are deferred to the changes that introduce those workflows or CI.
- **ARD-SYS-001..006, ARD-CTL-004, ARD-CTL-009..019, ARD-MNT-001..010, ARD-MLG-001..009, ARD-OPS-001..010** — runtime orchestration, domain analysis, A2A exchanges, scoring, operational impact analysis, and specialist behavior are outside this shared-foundation change.
- **ARD-TST-004, ARD-TST-006 onward** — scoring and complete end-to-end multi-agent scenarios require later Controller/specialist capabilities; this change covers only the foundation-level contract and gate tests.
- **ARD-RUB-005..012** — peer-review, Go/No-Go, human redirection, sponsor demonstration, and readiness evidence are project delivery activities, not shared runtime behavior.

### Out of Scope

- **ARD-PRN-001..006** — no agent recommendation or reasoning is implemented; the advisory-only/no-execution boundary and evidence-integrity principles remain binding constraints.
- Live enterprise connectivity and any operational write operation are out of scope under **ARD-SYS-008, ARD-SEC-002, ARD-GOV-008**.
- Standalone Risk, Recommendation, Report, Inventory, or Logistics agents remain out of scope under the root proposal’s ADR-001 and **ARD-SYS-002..005**.

No ARD deviation is requested.

## Rubric and Capability Coverage

| Rubric checkbox / proposal capability | Foundation support | Retained evidence | Verification | Human responsibility |
|---|---|---|---|---|
| Phase 2: OpenSpec proposal, design, spec delta, implementation checklist; Pydantic models and tool contracts | Versioned shared-foundation spec, Pydantic boundary models, typed tool result and error envelopes | This proposal, capability spec, design, tasks, model/contract docs | Requirement-to-model and requirement-to-test mapping; contract tests | Review scope and confirm contracts match domain owners’ needs |
| Phase 3: schema validation, structured outputs, explicit failures, partial data, no secrets | Deterministic validators, explicit evidence state, typed settings, redacted structured logs, mock adapters | Test results and sanitized structured event examples | Valid/invalid model tests; stale/conflicting/missing-data and failure tests | Validate business meaning, safety constraints, and accepted risks |
| Phase 4: output validation, unavailable tools, low confidence, regressions | Reusable pytest fixtures and deterministic adapter failure modes | Focused test summary and fixture scenario names | Contract, boundary, degraded-result, trace, and approval-gate tests | Review evidence and sign off on intended escalation behavior |
| AOG intake and evidence contracts | Pydantic case, evidence, confidence, and validation-error models | Schema definitions and validation test results | Required-field, provenance, freshness, and fact/assumption separation tests | Confirm source trust and freshness semantics |
| Typed enterprise tool boundary | Read-only adapter protocol and deterministic local/mock adapters | Request/result contracts and mock fixture records | Valid, malformed, timeout/unavailable, and structured-error tests | Approve any future live adapter and its permissions separately |
| Human approval and auditability | Human-decision record model, approval-required policy contract, event envelope with case/trace IDs | Audit-event examples without sensitive data | Tests prove agent/tool result and confidence cannot constitute approval | Authorized operational and airworthiness decision-makers retain all approval authority |

Installation or scaffolding alone is not evidence of behavior; retained verification must show these contracts and safeguards working.
