# Design

## Context

See `proposal.md` for motivation and scope and `specs/recovery-orchestration/spec.md` for observable behavior. The repository has shared Pydantic case, agent-result, tool, evidence, audit, confidence, and human-decision contracts; Maintenance and Materials & Logistics expose asynchronous `assess` boundaries; the H3/H4 peer workflow accepts a caller-supplied recorder; Operations exposes a typed request and deterministic per-candidate result. No Controller runtime or case context owner exists yet. The existing human gate returns pending when no matching human decisions have been recorded.

## Goals / Non-Goals

**Goals:**

- Own a case-scoped asynchronous workflow from validated intake through an unranked, evidence-complete handoff.
- Reuse specialist and Operations contracts and preserve candidate identity across every invocation/result.
- Make source health, routing, failures, timeouts, evidence gaps, conflicts, and human gate state observable and isolated by case.
- Run deterministically under local/mock adapters and fake agents without a live model or airline system in tests.

**Non-Goals:**

- Weighted scoring, relative ranking, close-score behavior, final recommendation prose, or decision-brief rendering.
- Human decision collection or changing the shared human approval contract.
- Replacing Maintenance, Materials & Logistics, or Operations domain reasoning with Controller logic.
- Live integrations or operational writes.

## Decisions

### Deterministic orchestration with a bounded ADK boundary

A typed Controller orchestration service owns intake validation, routing, candidate construction, timeouts, fan-out, result validation, aggregation, conflict state, and handoff status. A thin Google ADK Controller entry-point delegates to this deterministic boundary; any model-assisted description is bounded to evidence-grounded context and cannot alter routing, candidate identifiers, source values, confidence arithmetic, compliance results, approval state, or operational actions. Direct specialist invocation remains behind protocols so integration tests use fakes. This was selected over LLM-directed tool/routing loops because ARD-PRN-003 assigns validation and repeatable routing to deterministic logic and prevents prompt content from controlling permissions (ARD-PRN-003..005, ARD-TEC-002/005, ARD-SEC-003..005).

### Routing is an invocation allowlist

The validated routing decision is the sole allowlist for specialist fan-out. An omitted role is never called. For a selected role with an explicitly unavailable source-health record, the Controller records a structured candidate-local failure and skips invocation; partial, stale, or conflicting health remains attached as warning/missing-data state and lowers confidence. Unknown health remains explicitly unknown rather than being promoted to available. The exact route and its source-health records are carried into the final handoff so downstream consumers can see the invocation plan and its effect (ARD-CTL-003..004/008, ARD-GOV-004..005, ARD-RES-003..006).

### Routing is an invocation allowlist

The validated routing decision is the sole allowlist for specialist fan-out. An omitted role is never called. For a selected role with an explicitly unavailable source-health record, the Controller records a structured candidate-local failure and skips invocation; partial, stale, or conflicting health remains attached as warning/missing-data state and lowers confidence. Unknown health is preserved as unknown rather than promoted to available. The decision and health records are carried into the final handoff so downstream consumers can see both the invocation plan and its effect (ARD-CTL-003..004/008, ARD-GOV-004..005, ARD-RES-003..006).

### Candidate fan-out and Operations evaluation

The Controller first validates the base case and source bundle, then deterministically constructs supported repair-original, repair-preferred/alternate, swap, and delay candidates with stable option IDs. Unsupported candidate inputs remain missing rather than being filled with estimates. For every candidate, Maintenance and Materials & Logistics are invoked concurrently with candidate-specific inputs; their direct H3/H4 peer exchange is correlated to the case and appended through a Controller-owned `CaseContextRecorder` adapter. The Controller validates both shared `AgentResult` envelopes and role payloads and verifies evidence references before preparing Operations input. Operations is invoked once per candidate using a one-candidate `OperationsRequest`, so its existing agent can retain one consistent domain contract while returning a candidate-specific `OperationsOutcome`. Bounded agent timeouts and bounded inner tool retries use existing settings and request IDs. This satisfies the pre-ranking portion of ARD-CTL-018 while avoiding shared mutable state across candidate tasks (ARD-CTL-006/008/018, ARD-SYS-004, ARD-RES-005/007, ARD-NFR-001..003).

### Case context and append-only trajectory

A Controller-owned, case-isolated context store holds the validated intake, routing decisions and reasons, source-health results, candidate IDs, agent/tool outcomes, H3/H4 records, conflicts, confidence dispositions, and final handoff status. Context writes are append-only events with case/trace/correlation IDs and timestamps. The Controller adapter implements the existing H3/H4 recorder protocol rather than allowing the peer workflow to own workflow state. A context append failure yields an incomplete structured result and prevents a complete handoff. Events contain concise rationale and evidence references, never private chain-of-thought or unrelated case data (ARD-CTL-005, ARD-SYS-002/004, ARD-OBS-001..004, ARD-SEC-007/009, ARD-RES-003/007).

### Aggregation, compliance, and approval boundary

The aggregator accepts only validated results and preserves each candidate's source-backed values, assumptions, unknowns, warnings, costs, and Operations assessment. Conflicting estimates retain both values and evidence references and force escalation regardless of aggregate confidence. Confidence is deterministic: use the minimum confidence across required results for a candidate, cap or lower it for partial/missing results according to shared policy, and use the shared confidence assessment for the preferred/provisional/escalation disposition. Compliance eligibility is evaluated before the handoff; a failed or unknown required approval/authorization/traceability check excludes the candidate with an explicit reason. Output is an unranked list with no score/rank/recommended winner. The handoff is always pending human review; the shared approval gate may validate supplied decision records, but orchestration cannot create an approval or execute the selected action (ARD-CTL-006..008/017, ARD-GOV-001..008, ARD-SEC-001..003/008).

### Failure handling and security

Invalid intake produces field-level findings and no downstream call. A specialist timeout, malformed result, missing evidence, Operations failure, or context-append failure is represented with structured error/warning data and an affected-analysis marker. A failed candidate does not erase results for other candidates; the case cannot be marked complete if required analysis is absent. Retrieved source data is validated as untrusted; only role-allowlisted read tools are passed to agents. Timeouts and concurrency are bounded by typed settings, and each case has isolated state (ARD-DAT-008..010, ARD-RES-002..007, ARD-SEC-001..007, ARD-NFR-001..002).

### Verification

Contract tests cover valid/invalid versioned intake, context events, routing decisions, and the unranked handoff. Deterministic integration tests use fake Maintenance/M&L agents and mock Operations adapters to cover normal candidate fan-out, per-candidate correlation, H3/H4 persistence, Operations timeout, partial/missing specialist results, malformed evidence references, conflict escalation, compliance exclusion, case isolation, and pending human approval. No test makes a live model or network call (ARD-TST-001..003/005/007..009).

## Risks / Trade-offs

- **[Per-candidate fan-out increases latency and tool calls]** → Bound candidate count and concurrency, apply configured timeouts, and retain per-candidate failure status instead of silently dropping work (ARD-NFR-001..002).
- **[Candidate construction may be mistaken for ranking]** → Use stable IDs and deterministic eligibility only; preserve results in input order and prohibit score/rank/recommended-winner fields in this handoff (ARD-SYS-005, ARD-CTL-011..016).
- **[Shared case context may become a second workflow owner]** → Keep the store case-scoped and append-only; Controller owns routing/state, while H3/H4 uses only a narrow recorder port (ARD-SYS-002/004, ARD-SEC-009).
- **[A single failed candidate can be confused with whole-case failure]** → Preserve both candidate and case statuses; mark the overall result partial/escalation when required analysis is unavailable (ARD-CTL-008, ARD-RES-004).

## Migration Plan

This is additive. No existing Controller runtime state requires migration. Use an in-memory case context and deterministic specialist/Operations fakes first; a future persistence or live-integration change can implement the same typed recorder and adapter ports. Rollback removes the Controller orchestration package and its tests without changing shared contracts or specialist behavior.
