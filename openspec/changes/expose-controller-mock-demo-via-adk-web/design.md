# Design

## Context

See [proposal.md](proposal.md) for motivation and [the capstone-demonstration delta](specs/capstone-demonstration/spec.md) for externally visible behavior. The repository already provides `ControllerWorkflow`, typed `ControllerAdkResponse`, a bounded Controller ADK wrapper, deterministic local Operations adapters, and an offline Controller CLI. It has no Controller ADK Web root or scenario-to-intake adapter.

## Goals / Non-Goals

**Goals:**
- Expose the existing deterministic Controller workflow through one Google ADK Web root agent.
- Restrict model-selected input to a finite set of named synthetic scenarios; the scenario adapter supplies all case and evidence values.
- Preserve the typed Controller response, case-correlated evidence/audit, escalation, and pending human gate in the Web result.
- Make Web startup fail safely when its required model credential is missing or still the documented placeholder.
- Keep tests independent of the model provider and enterprise systems.

**Non-Goals:**
- Accept arbitrary free-form case payloads or let the model invent evidence, estimates, scores, or approvals.
- Replace the existing offline CLI, add live airline integrations, persist demo cases across process restarts, or introduce operational write tools.
- Validate provider-side credential authenticity without an authorized model request.

## Decisions

1. **Use the existing Controller ADK response boundary.** The Web root is built with `build_controller_adk_agent` and a `ControllerWorkflowPort` wrapper. The wrapper accepts a named scenario, resolves it through a fixed allowlist to a versioned synthetic intake payload, and delegates to the real `ControllerWorkflow`. Unknown names become a structured failure; no scenario is inferred or fabricated. This keeps Web exposure thin and leaves orchestration, validation, compliance, scoring, ranking, and report assembly in their existing deterministic owners (ARD-TEC-002/005, ARD-CTL-001..019, ARD-DAT-001..010).

   **Alternative considered:** Let the model construct the full intake JSON from a prose request. Rejected because that would permit invented case facts and bypass deterministic fixture selection. The model may interpret which named scenario the presenter requested, but tool input and result content remain bounded to the allowlist.

2. **Compose synthetic specialist ports and local Operations adapters.** Maintenance and Materials & Logistics ports return fixed, typed, source-referenced results for the selected scenario; Operations uses the existing deterministic local adapters with fixed settings. The same `ControllerWorkflow` performs intake, fan-out, H3/H4 recording, aggregation, compliance, ranking, and report generation. A fixed clock and case/trace identifiers make repeated runs stable (ARD-SYS-008, ARD-CTL-005..008/018, ARD-TST-009).

   **Alternative considered:** Return a prebuilt report directly from the demo function. Rejected because it would bypass Controller intake, candidate orchestration, and the report boundary and could not establish the intended end-to-end use case.

3. **Use one ADK Web root and a single bounded tool.** Add `adk_agents/controller_agent/agent.py`; the root agent exposes the existing typed orchestration tool and returns its `ControllerAdkResponse` without model summarization replacing the structured result. Its instruction requires a supported scenario selection, forbids changed evidence/scores or operational action, and directs the user to choose a scenario when intent is ambiguous (ARD-TEC-002/005, ARD-SEC-001..003, ARD-PRN-001..002/006).

4. **Treat model traffic separately from enterprise data.** The Web UI requires a locally configured `GEMINI_API_KEY` for conversational selection. A startup preflight rejects missing or example-placeholder values without logging or substituting credentials. Only the scenario name and synthetic response may reach the model; no live airline, supplier, identity, or operational records are loaded. Offline tests call the ADK tool boundary directly and make no model/network request (ARD-DEP-001..002, ARD-SEC-006, ARD-TST-009).

5. **Retain case-scoped audit only for the demo process.** Each workflow uses the Controller's existing recorder interfaces with an in-memory store and fixed trace context. The structured report carries evidence references and human-gate state; process-local audit is not represented as durable production retention (ARD-OBS-001..004, ARD-SEC-009, ARD-DEP-003).

6. **Expose failures as failures.** Invalid scenario names, invalid synthetic intake, unavailable/malformed source fixtures, and Controller exceptions return the existing structured failure response or a degraded Controller result. The ADK layer must not synthesize a successful report or clear conflicts/warnings. Approval stays pending for every scenario (ARD-DAT-008..010, ARD-RES-001..007, ARD-GOV-004..008).

## Risks / Trade-offs

- **The model selects the wrong named scenario** -> Keep the scenario vocabulary finite, return the exact selected scenario in the typed response, and ask for clarification rather than constructing arbitrary intake.
- **A developer later replaces synthetic ports with live sources** -> Keep the adapter factory private to the demo package, document the synthetic boundary, and require separate security/architecture review before any live connector is introduced.
- **A typed tool result is paraphrased or altered by model output** -> Use the existing response schema and skip summarization so the structured workflow result remains authoritative.
- **Demo audit is mistaken for durable audit retention** -> Label its store as in-memory/demo-only and make no persistence or production-readiness claim.
- **Credential validity is mistaken for live readiness** -> Validate only presence/non-placeholder form locally; explicitly defer provider authentication and do not make provider calls in tests.

## Migration Plan

No data migration or dependency change is required. Add the Controller ADK Web entry point and scenario wrapper without changing the existing Operations Web app or offline CLI. Start with `uv run adk web adk_agents` after configuring a local model credential; verify each scenario through the ADK Web UI. If a regression occurs, remove/disable the Controller Web root, keep the offline CLI and existing Operations demo intact, and rerun focused Controller/ADK tests plus repository verification before re-enabling it.
