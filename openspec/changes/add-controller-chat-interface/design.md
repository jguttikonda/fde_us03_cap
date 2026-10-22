# Design

## Context

The repository has typed Maintenance, Materials & Logistics, and Operations assessments and one ADK Web entry point for Operations. It does not yet have a Controller runtime, a case-level workflow, or a user-facing intake contract. See `proposal.md` and the two capability specs for scope and observable behavior.

Constraints: the ARD is authoritative; the chat is advisory-only; specialist and adapter boundaries remain typed; deterministic local/mock adapters are used; no operational writes or live airline integrations are introduced. The existing `incidents/mock_data/` files are untracked user-visible work from this conversation and must be preserved and consumed read-only.

## Goals / Non-Goals

**Goals:**
- Provide an ADK Web root agent that can accept conversational case details and return an evidence-backed Controller brief.
- Reuse existing specialist assessment contracts and deterministic mock adapters where practical.
- Keep intake validation, candidate construction, compliance, confidence handling, scoring, and report assembly deterministic and independently testable.
- Keep chat session context tied to one case and expose understandable errors and degraded states.

**Non-Goals:**
- Build a custom frontend, production API, authentication/authorization service, persistent case database, or production deployment.
- Connect live airline systems or add write-capable tools.
- Let the LLM certify airworthiness, make the deterministic ranking, approve options, or execute actions.

## Decisions

### ADK Web entry point over a custom web application

Add a distinct Controller agent package under `adk_agents/` and expose it as the ADK Web root agent. This follows the existing Operations demo pattern and provides the requested local chat UI without introducing an optional web framework. A custom React/FastAPI interface would add a separate service and security surface without being required for this capstone prototype. The existing Operations Web entry point remains available for specialist-only demonstrations.

### Chat model as a bounded interface; Controller workflow as deterministic application logic

The chat agent may interpret user prose into a proposed typed intake and explain a validated result. It calls a narrow Controller workflow boundary for validation and assessment. The workflow, not free-form model output, owns routing policy, result validation, evidence aggregation, conflict detection, compliance exclusions, confidence disposition, scoring, and final brief fields. The model cannot alter computed fields or represent a user message as an approval. This satisfies ARD-PRN-003..005, ARD-CTL-001..019, and ARD-SEC-008.

### Candidate workflow uses validated specialist contracts

Add Controller-specific Pydantic contracts for case intake, workflow status, candidate state, compliance exclusions, score factors, and the final decision brief. Invoke Maintenance and Materials & Logistics for supported repair candidates, record their peer exchange in case context, then provide candidate readiness to Operations. Specialist outputs must be validated before use. Keep evidence IDs, timestamps, assumptions, warning states, and missing-data values through aggregation. Do not translate missing evidence into a successful default. This reuses current specialist contracts instead of creating a parallel domain format (ARD-TEC-003, ARD-PRN-007..008, ARD-CTL-005..008).

### Compliance gate precedes deterministic scoring

Build candidate options from available evidence, exclude any candidate that lacks documented approval or part authorization/traceability, and retain exclusion reasons. Score only eligible options using the ARD 30/30/30/10 weights. Unit tests cover normalization, weights, cost inputs, stable ordering, and the two-percentage-point close-score rule. The LLM can explain the resulting brief but cannot re-rank options (ARD-CTL-011..019, ARD-TST-004).

### Read-only tools and deterministic fixtures

Use existing role-allowlisted read-only adapters and the saved synthetic fixtures as local test/demo inputs. Any fixture must be labeled synthetic; scenario-specific ETAs must not be reused across mismatched scenarios. Do not add purchase, reservation, shipping, flight-booking, or aircraft-assignment operations. Tool failures and stale or partial responses become structured warnings and affect the result status and confidence (ARD-SEC-001..005, ARD-RES-002..007).

### Chat response is a view of the validated report

Render the structured decision brief into a concise, plain-language response while preserving ranks, numeric fields, evidence references, exclusions, confidence, and required approvals. The chat should show a short summary first and details for ranked alternatives, risks, assumptions, and missing information. It must say the result is advisory and must not claim that a plan has been approved or executed (ARD-CTL-016, ARD-GOV-001..008, ARD-PRN-001..002).

### Case-scoped session and audit handling

Use the ADK conversation/session identifier only as a transport context; establish and validate an explicit case ID for each assessment. Do not share case findings across conversations. Emit existing structured, correlated audit events for intake, routing, adapter outcomes, conflicts, escalation, scoring, and brief completion without logging secrets, unnecessary sensitive content, or private model reasoning (ARD-CTL-005, ARD-RES-007, ARD-OBS-001..004, ARD-SEC-006..009).

### Testing without model or network calls

Test the workflow with fakeable prompt boundaries and deterministic adapters, following existing tests. Add schema tests, unit tests for compliance and scoring, chat/session tests, and end-to-end synthetic scenarios for normal, local/remote/unavailable parts, missing evidence, failure, conflict, low confidence, close scores, and human approval. Model/network use is not required in automated tests (ARD-TEC-008..009, ARD-TST-001..009).

## Risks / Trade-offs

- A local ADK Web prototype is not a production user interface and provides no production authentication -> Document this clearly and keep the launch local; require a separately reviewed design before deployment.
- LLM interpretation of conversational intake can omit or misread a field -> Validate typed fields deterministically, show the extracted case back to the user, and ask for missing or ambiguous details before running specialists.
- Current specialist contracts do not provide a complete Controller contract -> Add Controller-owned versioned contracts and integration tests; do not use free-form specialist text as a replacement.
- The example mock scenarios are not interchangeable -> Select the matching scenario explicitly, retain fixture provenance, and surface missing or mismatched readiness evidence.
- No Controller implementation currently calculates the decision brief -> Treat all score outputs as computed by new deterministic code, with independently tested calculations; do not reuse illustrative scores in `controller_agent.json` as evidence.

## Migration Plan

No existing runtime is replaced. Add the Controller package and ADK Web entry point alongside the existing Operations demo, document local startup and synthetic test prompts, and keep current agent entry points intact. Rollback consists of removing the new entry point and Controller package; existing specialist agents and fixtures remain unchanged.

## ARD Traceability

- Intake and typed boundaries: ARD-TEC-003, ARD-PRN-007, ARD-CTL-001..002, ARD-SEC-004.
- Routing, shared context, and specialist results: ARD-PRN-008, ARD-CTL-003..010, ARD-RES-003..007.
- Compliance, scores, and brief: ARD-PRN-003..006, ARD-CTL-011..019, ARD-GOV-001..005, ARD-CTL-016.
- Human gate and read-only security: ARD-PRN-001..002, ARD-GOV-006..008, ARD-SEC-001..009.
- ADK, testing, configuration, audit: ARD-TEC-002..005, ARD-TEC-008..009, ARD-TEC-014, ARD-OBS-001..004, ARD-TST-001..009.
- MCP transport (ARD-TEC-006) is not added because this local demonstration does not introduce a new cross-process MCP boundary. No ARD deviation is requested.