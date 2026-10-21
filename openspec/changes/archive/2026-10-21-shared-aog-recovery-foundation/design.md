# Design

## Context

See [proposal.md](./proposal.md) for motivation and scope and [specs/shared-foundation/spec.md](./specs/shared-foundation/spec.md) for the behavior contract. The repository currently contains proposal, agent-contract, rubric, and ARD documents but no application package or capability specs. The ARD is normative; requirements in this design are grounded in ARD-DAT, ARD-TEC, ARD-SYS, ARD-GOV, ARD-SEC, ARD-RES, ARD-OBS, ARD-NFR, and ARD-TST.

## Goals / Non-Goals

**Goals:**

- Establish an independently testable shared package boundary for typed contracts, deterministic validation, settings, adapter interfaces, and observability.
- Retain ADK as the approved agent/tool/session framework boundary while leaving specialist reasoning and Controller orchestration for later changes.
- Make unknown, stale, conflicting, failed, and partial results explicit and correlated to the AOG case.
- Keep enterprise adapters read-only and replaceable without changing shared request/result contracts.
- Keep human approval outside agent and tool outputs and test the no-bypass invariant.

**Non-Goals:**

- Implement any Controller or specialist agent reasoning, scoring, routing, or recommendation synthesis.
- Connect to live airline, inventory, maintenance, logistics, or operations systems.
- Add operational write tools, an API/UI, database, message broker, vector store, container platform, MCP boundary, or telemetry exporter.
- Define source-specific freshness durations not established by a domain owner or source contract.

## Decisions

### Package and responsibility boundaries

Use a `src`-layout Python package with small, separable modules:

```text
pyproject.toml
src/aog_recovery/
  contracts/       # Pydantic case, evidence, result, tool, error, approval, event models
  validation/      # deterministic intake, result, evidence, and approval policy checks
  adapters/        # typed read-only protocols and local/mock implementations
  config.py        # pydantic-settings configuration
  observability/   # structured logging, redaction, and correlation context
  adk/             # shared ADK integration boundary; no specialist agent definitions here
tests/
  conftest.py      # reusable case/evidence/result/tool fixtures
  contracts/
  validation/
  adapters/
  observability/
```

Keep contracts free of adapter implementations and model-provider calls. Validation accepts typed values and returns explicit findings. Adapter implementations depend on the contracts, not the reverse. ADK-facing integration is a thin boundary over the same contracts; any later Controller or specialist owns its reasoning and agent-specific tools in a separately scoped capability. This separation addresses ARD-NFR-004 and ARD-TEC-002/005 without introducing a parallel agent framework.

### Versioned Pydantic boundary models

Use Pydantic 2 models with strict input handling for externally supplied or cross-component data. Every serialized boundary envelope exposes `schema_version`. Use enums or constrained values for statuses and identifiers; do not allow unknown fields or invalid confidence values to pass as valid.

The shared types should include:

- `AogCase`: unique `case_id`, `aircraft_id`, `event_type`, `defect_summary`, `location`, `event_at`, `created_at`, schema version, and trace context. Required intake values are not filled with business defaults.
- `Evidence`: evidence identifier, source/system, retrieval time, freshness/validity state, claim supported, structured content/reference, and warnings. Represent confirmed facts separately from assumptions, unknowns, and conflicts.
- `AgentResult`: common agent identity/status/summary/confidence/assumptions/evidence-reference envelope plus an explicitly role-specific payload. Do not define specialist decision logic or imply that a result approves an action.
- `ToolRequest` and `ToolResult`: request ID, case and trace context, contract version, source/time, outcome, warnings, and typed data on success or structured error on failure. Do not use a success value when an adapter failed.
- `StructuredError`: stable category, component, message safe for logs, retryability, and case impact; omit secrets and raw sensitive payloads.
- `HumanDecisionRecord`: case ID, action, selected option when applicable, reviewer identity or test identity, timestamp, rationale, recommendation version, and decision type. Approval roles remain distinguishable.
- `AuditEvent`: timestamp, event type, case/trace IDs, component, status, schema version, and concise safe details.

Pydantic enforces shape and primitive constraints; deterministic validators enforce cross-field and policy rules. Keep these layers separate so schema parsing cannot be mistaken for business validation (ARD-DAT-001..011, ARD-CTL-001/002/006, ARD-RUB-004).

### Deterministic evidence, confidence, and approval rules

Validation returns typed field-level findings instead of coercing invalid inputs. Missing required evidence, stale evidence, and contradictions remain distinct statuses and are retained with source references. Freshness is evaluated against explicit source/configured validity metadata; absent freshness policy must be reported as unknown rather than inventing a TTL.

Confidence is normalized to `[0.0, 1.0]`. A deterministic policy labels `>= 0.70` preferred-but-awaiting-human-approval, `[0.50, 0.70)` provisional, and `< 0.50` requiring escalation. Material conflict independently defers approval regardless of score. Do not compute a case-level aggregate confidence in this foundation. Approval state comes only from a valid human decision record; for plans containing repair or part decisions, both the Ops lead and Maintenance/airworthiness authority are required. No test, high-confidence, partial-data, or error path can mark a plan approved or execute an action (ARD-GOV-001..008, ARD-TST-005).

### Tool adapters and future integration seam

Define typed, role-allowlisted, read-only adapter protocols around each future data domain. The initial implementations are deterministic in-memory/local mocks that accept explicit fixture data and can simulate unavailable, timeout, stale, malformed, and conflicting results. A future live adapter may implement the same protocol, but must add its own separately approved change for credentials, permissions, transport, timeouts/retry behavior, security review, and integration verification. No live endpoint or write method is added here.

Validate adapter responses as untrusted external input before returning them. Failures use `StructuredError` and an explicit failed/degraded status. If retries are later used, they are bounded and keyed to the same request ID for idempotency; a retry must not erase the original failure or hide fallback use (ARD-SYS-007..009, ARD-SEC-001..005, ARD-RES-001..007).

### Configuration and dependency policy

Use `pydantic-settings` for typed, environment-loaded settings: adapter mode, bounded tool/agent timeout defaults, and non-secret policy/configuration values. Secrets are read only through environment or a future approved secret provider and are never serialized or logged. Invalid configuration fails explicitly at load/startup. The implementation phase must verify supported dependency versions before recording compatible ranges in `pyproject.toml`, and document a single reproducible install workflow. Keep dependencies to the ARD-required Python, Google ADK, Pydantic 2, `pydantic-settings`, pytest, and Ruff baseline; add conditional tooling only when a specific capability requires it (ARD-TEC-001..014, ARD-NFR-001/006/007).

### Correlation, structured logging, and audit

Create or accept one trace/correlation identifier at the case boundary and propagate it with the case ID through ADK-facing calls, tools, adapter results, and events. Use standard-library `logging` with structured JSON serialization. Emit allowed event types for intake/validation, tool invocation/result, failure/degradation, conflict, escalation, and human decisions. Apply redaction before serialization; log source identifiers, outcome, warnings, and concise rationale, not secrets, unnecessary sensitive operational data, or private chain-of-thought. Preserve append-oriented audit records and the recommendation version linked to human review; the foundation does not require a database or external telemetry system (ARD-DAT-003, ARD-SEC-006..009, ARD-OBS-001..004).

### Reusable fixtures and focused tests

Provide shared pytest fixtures for a valid AOG case, source-backed evidence, agent result, success/failure tool results, trace context, human decisions, and deterministic local adapters. Parameterized variants cover missing fields, invalid schema versions, stale/partial/conflicting evidence, confidence boundary values (`0.49`, `0.50`, `0.69`, `0.70`), malformed adapter results, timeout/unavailable sources, and missing approval roles. Keep fixture data synthetic and deterministic. Tests verify exact serialized contract shape, validation findings, correlation propagation, redaction, read-only behavior, and that approval state cannot be inferred from agent output (ARD-TEC-008/009, ARD-TST-001..003/005, ARD-RUB-001..004).

## ARD Requirement Mapping

| ARD requirements | Design response |
|---|---|
| ARD-TEC-001..005, 008..014 | Python `src` package, Google ADK boundary, Pydantic 2 and typed settings, pytest/Ruff, minimal declared dependencies, version verification, reproducible setup. |
| ARD-SYS-007..009 | Typed read-only adapter protocols, deterministic local mocks, documented replacement seam. |
| ARD-DAT-001..010, 012 | Versioned strict boundary models; explicit case, evidence, confidence, error, tool, and event fields; unsupported input rejected. |
| ARD-CTL-001..003, 005..008 | Shared intake/result validators and explicit source-health, case-context, missing-result and conflict representation; no Controller workflow implementation. |
| ARD-GOV-001..008 | Threshold policy, independent conflict escalation, typed human decisions, both approval roles where required, no bypass. |
| ARD-SEC-001..009 | Least-privilege allowlisted read-only adapters, untrusted-response validation, secret/redaction controls, no unsafe airworthiness claims, append-oriented audit. |
| ARD-RES-001..007 | Explicit structured adapter and agent-facing failures, visible stale/fallback indicators, bounded/idempotent retry expectations, case isolation. |
| ARD-OBS-001..004 | Structured correlated events with required metadata and concise observable rationale, excluding private reasoning. |
| ARD-NFR-001..007 | Configurable bounded timeouts, bounded execution, determinism, module boundaries, local portability, externalized settings and declared dependencies. |
| ARD-TST-001..003, 005; ARD-RUB-001..004 | Requirement-mapped contract and failure tests, partial/conflict/confidence fixtures, no-approval-bypass proof, model/spec/test consistency. |

ARD-TEC-006/007, ARD-TEC-017..020, ARD-TST-004/006+, specialist-domain requirements, scoring, live integration controls, and delivery evidence are deferred as described in the proposal; they are not weakened. No ARD deviation is proposed.

## Risks / Trade-offs

- **[Shared contracts can overfit current agent drafts]** Keep a small common envelope and role-specific payloads; derive fields from the agent contract and version all serialized boundaries rather than forcing one specialist schema on all agents.
- **[Versioned models add migration work]** Start with an explicit schema version and reject unsupported versions. Define compatibility/migration policy in a later change before persisted cross-version data is introduced.
- **[Mock adapters may be mistaken for production integrations]** Label adapter mode and source explicitly in results and events; prohibit live connectivity and write operations in this change.
- **[Trace/logging can expose sensitive data]** Use synthetic fixtures, safe structured fields, and redaction at serialization boundaries; test secret and sensitive-value exclusion.
- **[Approval records may be mistaken for execution capability]** Model human decisions as records only and expose no operational write method; test that decisions cannot invoke actions.
- **[Python and ADK versions may have shifted]** Verify supported versions during implementation before pinning dependencies; keep framework use behind narrow boundaries.

## Migration Plan

This is the initial application foundation; there is no existing application package or persisted contract data to migrate. Add the package, dependency metadata, settings, fixtures, and tests as an additive change. Rollback consists of reverting this change before downstream capabilities depend on the contracts; once adopted, contract changes must use an explicit schema-version compatibility plan. Do not introduce database migrations or deployment steps.

## Open Questions

None that block the proposed contract or package boundaries. Source-specific freshness limits and any future live-integration authentication/permissions must be determined with their owners in the corresponding integration change.
