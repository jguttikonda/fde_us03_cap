# Proposal

## Why

An AOG recovery option can preserve aircraft availability yet still disrupt flights, crews, customers, and package commitments. The Operations Agent needs a typed, evidence-grounded way to evaluate those impacts—including whether package loads can be protected within tail-specific capacity and cut-off windows—so the Controller and human reviewers can compare recovery options without relying on unsupported assumptions.

## What Changes

- Add a cohesive Operations impact-analysis capability covering affected flights, routes, schedules, fleet assignments, substitute aircraft, crew constraints, customer impact, active disruptions, and package load redistribution.
- Define deterministic schedule and assignment conflict checks, feasibility checks, impact classification, capacity/cut-off calculations, and per-option delay/swap cost estimates behind typed, read-only adapters.
- Return a structured, versioned Operations result with evidence provenance, assumptions, missing or stale data, risks, unprotected packages, option-level impacts, recommendation rationale, confidence, and next steps.
- Make timeouts and unavailable or conflicting evidence visible as structured degraded or provisional results; do not silently substitute successful-looking values.
- Add deterministic mock adapters and unit/contract test scenarios for normal, partial, conflict, timeout, degradation, security-boundary, and human-approval behavior.
- Keep cross-agent orchestration, Controller aggregation and weighted ranking, final report generation, and all operational execution out of scope.
- No ARD deviation is requested.

## Capabilities

### New Capabilities

- `operations-impact-analysis`: Produce evidence-grounded flight, fleet, customer, crew, schedule, cost, and package-load impact assessments for Controller-supplied recovery options.

### Modified Capabilities

- None. The repository has no existing capability specifications.

## Impact

- **Code and contracts:** New Operations domain models, deterministic impact and redistribution logic, an ADK-based specialist boundary, and typed tool adapters for flight operations, fleet assignment, crew/station planning, customer priority, disruption, and package-load data. Use deterministic local/mock integrations; use the supported MCP SDK only for adapters crossing an MCP process/service boundary.
- **Behavior and interfaces:** The Operations result is a domain assessment for later Controller aggregation, not a final system ranking or an approval. Option comparison remains bounded to Operations impact; the Controller retains system-wide ranking and final-report ownership. All integrations are read-only and cannot execute swaps, dispatch, bookings, or package transfers.
- **Verification:** Pytest contract and behavior tests use fixed fixtures and mock adapters, covering capacity by tail, package service levels and cut-offs, unprotected remainder, conflicts, missing/stale data, timeouts, and policy boundaries.

## ARD Traceability

### Addressed

| ARD requirements | Rationale |
|---|---|
| ARD-OPS-001..009 | Defines the required operational inputs, deterministic validation and impact classification, repair/swap/delay option analysis, structured result, time-sensitive-data treatment, material customer trade-offs, conflict explanations, and package redistribution within tail capacity/service/cut-off constraints with unprotected packages included in impact and cost. |
| ARD-PRN-001..008 | Keeps recommendations advisory and human-owned; assigns calculations and checks to deterministic logic; bounds model reasoning; preserves evidence, assumptions, uncertainty, typed boundaries, and case-correlatable outputs. |
| ARD-SYS-001, 003, 007..009 | Implements the Operations specialist without adding an agent, enforces domain ownership, uses typed adapters, and supports deterministic local/mock integrations compatible with future adapters. |
| ARD-TEC-001..009 | Plans implementation in the required Python/Google ADK/Pydantic stack, with typed settings, governed model access, bounded asynchronous tool calls, pytest, and configured code-quality checks. MCP SDK use is conditional on an actual MCP process/service boundary. |
| ARD-GOV-001..008 | Preserves confidence thresholds, missing-data visibility, conflict deferral, and the human approval boundary; the Operations result never approves an option or authorizes action. |
| ARD-RES-002..007 | Defines visible Operations timeouts and structured agent failures, partial-result semantics, bounded/idempotent retry behavior, no silent fallback, and case isolation. Cached inventory behavior under ARD-RES-001 belongs to Materials & Logistics and is not introduced here. |
| ARD-SEC-001..008 | Limits adapters to least-privilege, allowlisted, read-only access; validates untrusted inputs; resists prompt injection; protects secrets and logs; and prohibits unsupported airworthiness or regulatory claims. |
| ARD-OBS-001..005 | Emits traceable structured validation, tool, completion, conflict, fallback, and escalation events with case/correlation and schema metadata, without requiring private chain-of-thought. |
| ARD-NFR-001..007 | Uses configurable timeouts and bounded execution, deterministic calculations, clear module boundaries, local portability, externalized configuration, and declared dependencies. |
| ARD-TST-001..003, 005, 007..009 | Maps requirements to deterministic contract/agent/security/human-gate tests and regression evidence; fixed mocks and fixtures avoid real systems or model calls in unit tests. |
| ARD-OSP-001..005 | Preserves the required spec-driven artifacts, testable scenarios, traceability, and explicit non-removal of normative requirements. |

### Deferred

| ARD requirements | Rationale |
|---|---|
| ARD-SYS-002, ARD-CTL-001..019, ARD-TST-004 | Controller intake, orchestration, aggregation, compliance gate, weighted scoring, close-score handling, and final recommendation/report ownership are separate work. Operations will return option-level domain findings for later aggregation and will not implement or test Controller ranking. |
| ARD-SYS-004 and Maintenance/Materials & Logistics collaboration | Operations is a top-level specialist called by the Controller and does not introduce direct peer orchestration. |
| ARD-RES-001 | Inventory outage and cached-inventory fallback are owned by Materials & Logistics. Operations will report its own unavailable inputs and may not make a cache look current. |
| ARD-DEP-001 and project-level RAPID/sponsor approval deliverables | Runtime/deployment readiness and cross-project sign-off evidence are not Operations capability behavior; this change will identify evidence to retain, not claim completion. |

### Out of Scope

| ARD requirements | Rationale |
|---|---|
| ARD-SYS-005..006 and ARD-GOV-006..007 implementation | Final recommendation ownership, approval workflow, and approval-record persistence remain with the Controller/human-approval boundary. This capability only makes its result suitable for those later stages. |
| ARD-CTL-009..019 and final report generation | Final compliance gating, weighted ranking, close-score selection, and decision-brief rendering are explicitly excluded. |
| Any operational write or execution | This change adds analysis only; swaps, dispatch, schedule changes, bookings, package transfers, and other operations remain human-controlled and are not invoked by tools. |

No ARD requirement is weakened or contradicted by this proposal. Operations-originated recommendations remain advisory, evidence-backed, and subject to Controller aggregation and mandatory human approval.

## Rubric and Capability Coverage

| Rubric/capability area | Framework or implementation | Retained evidence | Verification | Human responsibility |
|---|---|---|---|---|
| Category 1: agent functionality and correctness; Phase 3 | Google ADK Operations specialist, Pydantic contracts, typed read-only adapters, deterministic impact and load calculations | Capability spec, contracts, mock fixtures, test results, structured sample outputs | Unit and contract tests for valid/invalid inputs, route/assignment conflicts, swap/delay options, cost, and package protection | Review feasibility and choose whether to escalate; no tool executes an operational action. |
| Category 2: spec-driven design quality; Phase 2 | OpenSpec capability requirements and scenarios | Proposal, capability spec, design, task checklist, ARD traceability | Validate OpenSpec artifacts and trace each requirement to scenarios/tasks | Peer review confirms scope and ARD alignment. |
| Category 3: engineering quality; Phases 3–4 | Python, typed contracts, pytest, Ruff, deterministic mock adapters | Test results, code-review record, regression fixtures | Contract, deterministic behavior, timeout/degraded, security, and regression checks | Review results and accept or reject engineering readiness. |
| Category 4: RAPID controls; Phase 5 | Existing project RAPID process; no new Operations approval authority | RAPID peer-review and Go/No-Go artifacts retained at project level | Verify the analysis is advisory, read-only, and does not bypass approval | Ops lead and Maintenance/airworthiness authority retain approval responsibilities where applicable. |
| Category 5: AI-assisted development practice; Phase 1 | Existing repository AI-development guidance and review process | Traceable OpenSpec artifacts, test evidence, and peer review | Review generated changes and verify behavior with deterministic tests | Team owns and validates all AI-assisted output. |
| Category 6: demonstration and communication; Phase 6 | Deterministic mock AOG scenarios and concise structured output | Rehearsable scenario inputs/results and demonstration notes | Demonstrate a normal case, a constrained package redistribution, and degraded/conflicting evidence | Sponsor-facing presenter explains limitations, uncertainty, and the human gate. |
| Operations impact analysis capability | `operations-impact-analysis` | Per-option evidence, assumptions, risks, costs, missing-data markers, and unprotected-package details | Requirement-to-scenario traceability and deterministic tests | Controller aggregates specialist results; authorized humans make operational decisions. |

The rubric checklist identifies RAPID and sponsor-demo artifacts as later project readiness evidence; installing a framework or passing unit tests alone will not be represented as proof of those controls.
