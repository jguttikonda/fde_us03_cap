# Proposal

## Why

The repository has an ADK Web entry point for Operations, but an end user cannot yet describe an AOG event in chat and receive a complete cross-functional recovery brief. A Controller-led chat would provide one understandable interface for collecting a case, coordinating the existing specialists, and presenting evidence-backed options while preserving human authority.

## What Changes

- Add a typed Controller workflow that validates chat intake, maintains case-scoped context, coordinates Maintenance, Materials & Logistics, and Operations, checks specialist results, detects conflicts, applies compliance before deterministic scoring, and returns an approval-ready decision brief.
- Add an ADK Web-discoverable Controller root agent so a user can describe an AOG event and receive a plain-language response backed by structured, validated results.
- Use the existing local/mock read-only adapters and synthetic fixtures for the demonstration. Ask the user for missing required inputs; keep missing, stale, conflicting, and unavailable evidence visible.
- Require human review and the appropriate operational and airworthiness approvals. The chat and agents do not execute repairs, move parts, change flights, or record approval on a human's behalf.
- Add deterministic tests for chat intake, orchestration, compliance, scoring, conversation/case isolation, failures, and the human gate; document local ADK Web startup and demo scenarios.
- No live airline integration, authentication system, custom frontend, or new infrastructure is introduced in this change.

## Capabilities

### New Capabilities

- `controller-recovery-workflow`: Case validation, specialist coordination, evidence/conflict handling, compliance gating, deterministic option scoring, and human-ready recovery briefs.
- `aog-chat-interface`: ADK Web chat entry point for AOG intake and Controller responses, with case-scoped context and clear validation, uncertainty, escalation, and approval messages.

### Modified Capabilities

None. Existing specialist contracts remain unchanged; the Controller consumes their validated inputs and results.

## Impact

- Python: new Controller orchestration and typed contracts under `src/aog_recovery/`; new ADK Web entry point under `adk_agents/controller_agent/`.
- Tests: Controller, chat interaction, integration, scoring/compliance, degraded evidence, and security boundary tests using local/mock fixtures.
- Documentation: local setup, ADK Web launch, sample prompts, limitations, and human approval behavior.
- Dependencies: reuse the existing Google ADK, Pydantic, pytest, and tooling; no new framework is planned.
- The ADK Web prototype is for local demonstration. Production UI, authentication, live-system integrations, and deployment hardening remain out of scope.

## ARD Traceability

- **Addressed:** ARD-TEC-002..005, ARD-TEC-008..009, ARD-TEC-014, ARD-TEC-017; ARD-PRN-001..008; ARD-CTL-001..019; ARD-GOV-001..008; ARD-RES-002..007; ARD-SEC-001..009; ARD-OBS-001..004; ARD-TST-001..009. The capability is explicitly local/mock and read-only, so tool health, typed boundaries, evidence state, human approval, auditability, deterministic ranking, and required failure/security scenarios are part of its acceptance criteria.
- **Deferred:** ARD-TEC-006 is deferred because this local prototype does not add a new cross-process MCP boundary; existing adapter boundaries remain in place. ARD-OBS-005 metrics and deployment/production operation are not needed for the local chat demonstration.
- **Out of scope:** Autonomous operational execution and production airline-system integration are prohibited by ARD scope and are not introduced. There are no requested ARD deviations.

## Rubric and Capability Coverage

| Rubric/checklist area | Capability and framework | Retained evidence and verification | Human responsibility |
|---|---|---|---|
| Category 1: Agent functionality; Phase 3 end-to-end agent | `controller-recovery-workflow`; Google ADK, Pydantic, existing specialist agents and deterministic adapters | Integration scenarios cover normal, local/remote/unavailable parts, missing/conflicting evidence, scoring, and specialist failures; pytest results retained | Review the brief and make all operational/airworthiness decisions |
| Category 2: Spec-driven design; Phase 2 OpenSpec conversion | Both capabilities; OpenSpec and versioned typed contracts | ARD-linked proposal, specs, design, tasks, contract tests, and traceability | Peer review scope, requirements, and trade-offs |
| Category 3: Engineering quality; Phase 4 testing | Both capabilities; pytest, Ruff, mypy, read-only tool boundary | Deterministic regression, boundary, security, failure, scoring, and human-gate tests | Review unresolved issues and test evidence |
| Category 5: AI-assisted development practice | Both capabilities; repository workflow and project instructions | Preserve implementation/review evidence required by the capstone process | Human review and redirection of AI-assisted work |
| Category 6: Demonstration and communication; Phase 6 | `aog-chat-interface`; local ADK Web and synthetic scenarios | Rehearsable chat prompts and sponsor-readable responses; demo notes state limitations | Explain the advisory boundary, caveats, and final decision ownership |