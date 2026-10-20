# OpenSpec Proposal Prompts

This document preserves the recommended OpenSpec proposal sequence for implementing the complete Aircraft-On-Ground (AOG) Recovery Coordinator scope described in:

- `docs/architecture-requirements.md`
- `docs/proposal.md`
- `docs/capstone_rubric_phase_checklist.md`
- `docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md`
- `docs/agent-proposals/controller-agent-proposal.md`
- `docs/agent-proposals/maintenance-agent-proposal.md`
- `docs/agent-proposals/inventory-agent-proposal.md`
- `docs/agent-proposals/operations-agent-proposal.md`
- `docs/agent-proposals/report-creation-agent-proposal.md`

## Governing Architecture Baseline

`docs/architecture-requirements.md` is the authoritative engineering baseline for every prompt in this document. Every generated OpenSpec proposal, design, capability specification, scenario, and task must:

- comply with the applicable ARD requirements
- cite applicable `ARD-<AREA>-<NUMBER>` identifiers
- include explicit traceability from requirements to scenarios and tasks
- identify deferred or out-of-scope ARD requirements with rationale
- surface any proposed deviation instead of silently weakening the ARD

These instructions supplement the enforcement rules in `openspec/config.yaml`.

## Recommended Change Sequence

```text
1. Foundation and contracts
          |
          +-------------------+
          |                   |
          v                   v
2. Maintenance/Inventory   3. Operations
          |                   |
          +---------+---------+
                    v
          4. Controller orchestration
                    |
                    v
          5. Reporting and approval
                    |
                    v
          6. End-to-end validation/readiness
```

Create, review, implement, verify, and archive each dependency layer before beginning a change that depends on it.

## 1. Establish the AOG Agent Foundation

Suggested change name:

```text
establish-aog-agent-foundation
```

Proposal prompt:

```text
/opsx-propose Establish the shared foundation for the AOG Recovery Coordinator.
Use docs/proposal.md, docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md, and
docs/capstone_rubric_phase_checklist.md as source material. Define the Google
ADK project structure, Pydantic models for AOG cases and agent outputs,
evidence and confidence contracts, deterministic validation, tool-result
contracts, configuration, logging, correlation and trace identifiers, and
reusable test fixtures. Keep the system advisory-only and require human
approval before any operational action. Use deterministic local or mock
adapters for external enterprise systems, with clearly documented extension
points for future live integrations. Do not implement any specialist agent
reasoning in this change.
```

Suggested capabilities:

- `aog-case-intake`
- `shared-agent-contracts`
- `tool-contracts`
- `decision-confidence`

Expected scope:

- Python and Google ADK project structure
- Shared AOG case model
- Shared agent request and result envelopes
- Evidence, assumption, warning, and confidence models
- Recovery option and decision-status enumerations
- Pydantic validation
- Tool invocation result and error contracts
- Correlation and trace identifiers
- Deterministic validation utilities
- Representative test fixtures
- Logging, configuration, and secret-handling conventions

## 2. Implement Maintenance and Inventory Analysis

Suggested change name:

```text
implement-maintenance-inventory-analysis
```

Proposal prompt:

```text
/opsx-propose Implement the Maintenance and Inventory analysis workflow using
the shared AOG contracts. Use docs/proposal.md,
docs/agent-proposals/maintenance-agent-proposal.md,
docs/agent-proposals/inventory-agent-proposal.md, and
docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md as the authoritative source
material. Cover repair feasibility, maintenance evidence, parts availability,
alternate sourcing, material readiness, lead time, uncertainty, MCP tool
adapters, deterministic guardrails, cached inventory fallback, conflict
handling, structured handoffs, and unit and contract tests. Ensure confirmed
facts, assumptions, stale data, and uncertainty remain distinguishable. Do not
implement Controller orchestration or final report ranking in this change.
```

Suggested capabilities:

- `maintenance-assessment`
- `inventory-sourcing`
- `maintenance-inventory-coordination`

Expected scope:

- Maintenance evidence collection
- Repairability and technical-feasibility assessment
- Inventory availability and sourcing assessment
- Work-order and maintenance-record tool contracts
- Stock, supplier, substitution, and transfer tool contracts
- Confirmed versus uncertain feasibility
- Material readiness and alternate sourcing
- Maintenance and inventory conflict handling
- Cached inventory fallback
- Structured outputs for the Controller
- Unit and contract tests

## 3. Implement Operations Impact Analysis

Suggested change name:

```text
implement-operations-impact-analysis
```

Proposal prompt:

```text
/opsx-propose Implement the Operations Agent using the shared AOG contracts.
Use docs/proposal.md, docs/agent-proposals/operations-agent-proposal.md, and
docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md as the authoritative source
material. Cover flight, route, fleet, schedule, customer, crew, aircraft-swap,
reroute, and delay impact analysis. Define MCP tool adapters, deterministic
schedule and assignment conflict checks, structured recommendations,
uncertainty handling, degraded results, timeout behavior, and unit and contract
tests. Ensure the output distinguishes evidence from assumptions and remains
suitable for later Controller aggregation. Do not implement cross-agent
orchestration or final report generation in this change.
```

Suggested capability:

- `operations-impact-analysis`

Expected scope:

- Schedule and route impact
- Aircraft assignment conflicts
- Swap and substitution options
- Delay and reroute evaluation
- Customer, crew, and fleet impact
- Operational risk and cost
- Tool timeout and degraded-result handling
- Structured recommendation for the Controller
- Unit and contract tests

Changes 2 and 3 may be proposed and implemented independently after change 1 has been completed and archived.

## 4. Orchestrate AOG Recovery Cases

Suggested change name:

```text
orchestrate-aog-recovery-cases
```

Proposal prompt:

```text
/opsx-propose Implement Controller-led orchestration for AOG recovery cases.
Use docs/proposal.md, docs/agent-proposals/controller-agent-proposal.md, and
docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md as source material, and use the
existing shared-contract and specialist-agent capabilities as dependencies.
Cover AOG case intake, required-field validation, routing, shared coordination
context, specialist invocation, result aggregation, partial agent failure,
missing evidence, confidence reduction, material conflict detection,
escalation, correlation and traceability, and human-approval enforcement.
Inventory evidence may be requested by Maintenance, but the Controller must
retain traceable ownership of routing and shared workflow state. Do not
implement final weighted option ranking or decision-report rendering beyond
the Controller-to-Report-Agent handoff.
```

Suggested capabilities:

- `recovery-orchestration`
- `agent-routing`
- `case-escalation`

Expected scope:

- AOG event intake
- Required-field validation
- Shared coordination context
- Specialist routing and execution
- Output aggregation
- Missing-agent and failed-agent behavior
- Domain conflict detection
- Confidence reduction
- Escalation rules
- Workflow traceability
- Controller tests

## 5. Deliver Ranked Recommendations and Human Approval

Suggested change name:

```text
deliver-ranked-recommendations-and-human-approval
```

Proposal prompt:

```text
/opsx-propose Implement ranked AOG recovery recommendations and human approval.
Use docs/proposal.md,
docs/agent-proposals/report-creation-agent-proposal.md, and
docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md as source material. Consume the
specialist findings supplied through the Controller. Cover candidate recovery
option construction, weighted option scoring, explainable trade-offs, evidence
references, assumptions, risks, warnings, uncertainty, closely ranked options,
provisional decisions, and approve, reject, or escalate actions. Produce a
structured decision-ready report and an auditable human decision record. The
Controller owns workflow completion and escalation; the Report Creation Agent
owns ranking, explanation, and report generation; the human owns final
approval. The system must remain advisory and must never execute an operational
action automatically. Include unit, contract, and workflow tests.
```

Suggested capabilities:

- `recovery-recommendation`
- `human-approval`
- `decision-reporting`

Expected scope:

- Candidate recovery option construction
- Weighted option scoring
- Repair, transfer, swap, reroute, and delay comparisons
- Closely scored option behavior
- Evidence, assumptions, risks, warnings, and trade-offs
- Provisional recommendation status
- Human approve, reject, and escalate workflow
- Auditable decision record
- Decision-report rendering
- Low-confidence and conflicting-data tests

## 6. Validate AOG Recovery Readiness

Suggested change name:

```text
validate-aog-recovery-readiness
```

Proposal prompt:

```text
/opsx-propose Validate the complete AOG Recovery Coordinator for capstone
readiness. Use docs/proposal.md, docs/capstone_rubric_phase_checklist.md, and
all files under docs/agent-proposals as acceptance-criteria sources. Add
end-to-end happy-path and degraded-mode scenarios, schema validation,
tool-contract tests, missing and conflicting-data tests, unavailable-tool and
timeout tests, regression checks, security and audit controls, environment and
deployment documentation, backout guidance, test evidence, RAPID Go/No-Go
artifacts, and sponsor-facing demonstration scenarios. Include the functional
cases in docs/proposal.md, including cached inventory fallback, conflicting
maintenance and operations estimates, and mandatory human choice when recovery
options fall within the documented close-score threshold. Verify that the
system remains advisory, explainable, traceable, least-privileged, and unable
to perform operational actions without human approval.
```

Suggested capabilities:

- `recovery-workflow-resilience`
- `security-and-audit`
- `deployment-readiness`
- `capstone-demonstration`

Expected scope:

- End-to-end scenarios
- Functional validation cases from the root proposal
- Partial, missing, stale, and conflicting data
- Inventory API unavailable
- Operations timeout
- Closely scored recovery options
- Schema and tool-contract tests
- Prompt-injection awareness and tool allowlisting
- Least-privilege and read-only checks
- Audit and trace verification
- Environment and deployment instructions
- Backout plan
- Test evidence
- RAPID Go/No-Go evidence
- Demo scenarios and sponsor-facing readiness

## OpenSpec Execution Cycle

Use this cycle for each change:

```text
/opsx-propose
      |
      v
Review proposal, design, specs, and tasks
      |
      v
/opsx-apply
      |
      v
Run tests and verify acceptance scenarios
      |
      v
/opsx-archive
      |
      v
Begin the next dependent change
```

Recommended execution order:

1. Propose, apply, verify, and archive `establish-aog-agent-foundation`.
2. Propose `implement-maintenance-inventory-analysis` and `implement-operations-impact-analysis`.
3. Apply, verify, and archive both specialist changes.
4. Propose, apply, verify, and archive `orchestrate-aog-recovery-cases`.
5. Propose, apply, verify, and archive `deliver-ranked-recommendations-and-human-approval`.
6. Propose, apply, verify, and archive `validate-aog-recovery-readiness`.

## Cross-Cutting Design Decisions

Apply these decisions consistently across the changes.

### Inventory routing

- The Controller owns workflow routing and shared workflow state.
- Maintenance may request Inventory evidence through the shared case context.
- Agent-to-agent interactions must remain visible in the case trace.

### Final synthesis ownership

- The Controller owns workflow completion, conflict handling, and escalation.
- The Report Creation Agent owns ranking, explanation, and report generation.
- A human owns final approval or rejection.

### Confidence and escalation

Use explicit confidence states:

```text
HIGH       = evidence is complete and has no material conflict
MEDIUM     = evidence is usable but has documented limitations
LOW        = a source is missing or stale, or material uncertainty remains
CONFLICTED = specialist outputs cannot be reconciled
```

Only qualifying `HIGH` or `MEDIUM` results may identify a preferred option. `LOW` and `CONFLICTED` results must require human escalation.

### Operational side effects

The implementation is advisory:

- It must not approve a maintenance work order automatically.
- It must not change an aircraft assignment automatically.
- It must not initiate an inventory transfer automatically.
- It must not delay or cancel a flight automatically.
- Human approval is required before any operational action.

### External integrations

For the capstone implementation:

- Define typed interfaces representing enterprise systems.
- Provide deterministic local or mock adapters.
- Document extension points for future live integrations.
- Do not require access to live airline systems for tests or demonstrations.
