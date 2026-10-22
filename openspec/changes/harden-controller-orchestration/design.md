# Design

## Context

See `proposal.md` for motivation and `specs/controller-runtime-integration/spec.md` for observable behavior. Routing and source-health enforcement are owned by `orchestrate-aog-recovery-cases`; this design starts at the routed specialist-invocation boundary. The current specialist ports accept a generic Controller request, while the existing agents accept `MaintenanceAssessmentInput` and `MaterialsLogisticsAssessmentInput`. Operations currently exposes synchronous `assess(OperationsRequest)` and its tool gateway is synchronous. The ADK Controller entry returns a dictionary from a tool but does not declare an output schema. Existing workflow tests use fakes and do not run two workflows concurrently. (ARD-CTL-006/008/018, ARD-RES-002/007, ARD-NFR-001..002)

## Goals / Non-Goals

**Goals:**

- Bridge candidate-scoped validated inputs into the unchanged specialist input models.
- Bound Operations calls and preserve timeout evidence per candidate.
- Constrain the ADK response to a typed advisory workflow envelope.
- Prove case isolation under concurrent end-to-end execution and correct the Controller traceability evidence.

**Non-Goals:**

- Changing Maintenance, Materials & Logistics, or Operations domain rules or prompts.
- Adding live enterprise sources, a database, operational write tools, ranking, or decision-brief generation.
- Collecting human approval. Every handoff remains pending human decision (ARD-GOV-006..008).

## Decisions

### Specialist adapters preserve the existing contracts

Keep the Controller's candidate correlation wrapper separate from specialist domain inputs. Candidate source data will carry validated role-specific `MaintenanceAssessmentInput` and `MaterialsLogisticsAssessmentInput` values (or a typed equivalent that can be losslessly validated into them). Narrow adapters call the existing agents with those models and return their existing `AgentResult`; candidate ID and request ID remain in the Controller result/context rather than being inserted into specialist domain facts. Missing domain inputs produce structured partial/failure results, never inferred default payloads. This avoids copying specialist logic into Controller and satisfies ARD-TEC-003, ARD-DAT-006/009, and ARD-CTL-006/018.

Alternatives considered: constructing large specialist input objects from generic evidence maps inside the workflow (rejected because source-to-field mapping is domain-specific and easy to silently omit); changing the Maintenance or Materials & Logistics agent APIs (rejected because their existing validated models already define the boundary).

### Operations receives an asynchronous bounded adapter

The Controller-facing Operations port will be asynchronous and deadline-controlled using typed settings. The adapter around the existing synchronous deterministic `OperationsAgent.assess` is isolated from the workflow service; timeout/cancellation, resource limits, and cleanup behavior are tested at that adapter boundary. If the current synchronous call cannot be interrupted safely, the adapter must use a bounded execution mechanism rather than letting timed-out work accumulate. A timeout yields a candidate-local `StructuredError`, missing Operations analysis, an audit event, and confidence reduction/escalation; other candidates continue. The Operations domain model and calculation remain unchanged (ARD-RES-002..005, ARD-NFR-001..002).

Alternatives considered: relying on the Operations tool gateway's retry loop as a deadline (rejected because retries do not bound a blocked synchronous call); catching only a raised `TimeoutError` from a fake port (rejected because this proves error formatting, not enforcement).

### ADK output is schema-constrained

The ADK Controller boundary will expose a versioned response model wrapping the deterministic workflow result and validation findings. `LlmAgent` output validation will require that schema; its instructions and tool set will remain limited to the deterministic workflow boundary. Tests construct the agent without a model call and validate successful and failure response shapes. The response contract itself contains no score, rank, winner, approval, or execution action. Deterministic validation and routing remain outside model judgment (ARD-TEC-002/005, ARD-PRN-003..005, ARD-SEC-003..005).

### Case execution remains isolated

Per-run objects own candidate state, timeout state, and intermediate outputs. Shared persistence is accessed only through the append-only case context port and events retain the case plus trace/correlation identifiers. A deterministic two-case integration test will run both workflows concurrently, force a failure in one, and assert that only that case becomes partial/escalated. No mutable global workflow accumulator is introduced (ARD-RES-007, ARD-OBS-001..004, ARD-SEC-009).

### Traceability evidence has one current home

The Controller evidence rows and event map will be consolidated into a dedicated Controller section/document. The shared-foundation verification's 74-test result remains labeled as historical foundation evidence; the new verification note records the current full-suite result and links to the Controller scenario suite. This is documentation-only and does not alter requirements (ARD-TST-001/008, ARD-TEC-019, ARD-RUB-002..004).

## Risks / Trade-offs

- **[Typed per-candidate specialist inputs repeat data across candidates]** → Keep the shared case evidence immutable and reuse references; create candidate-local typed request envelopes and test evidence resolution (ARD-DAT-003..006, ARD-RES-007).
- **[A timeout around synchronous Operations work may leave a worker running]** → Do not claim bounded execution until cancellation/worker containment is tested; keep the adapter read-only and bounded in concurrency (ARD-RES-002, ARD-NFR-001..002).
- **[ADK may add prose around tool output]** → Validate the final response schema and keep all eligibility, status, and approval state in deterministic workflow output (ARD-TEC-005, ARD-SEC-003/008).

## Migration Plan

This is additive and has no persisted runtime state to migrate. Existing `ControllerWorkflow` callers will be updated to provide typed specialist adapters and an asynchronous bounded Operations adapter. Rollback removes those adapters and the ADK response constraint without changing the existing specialist or Operations domain models. The run remains local/mock-only (ARD-NFR-005).

## Open Questions

None. The selected adapter and timeout constraints are required by the existing contracts and verification findings; they should not be deferred to implementation.