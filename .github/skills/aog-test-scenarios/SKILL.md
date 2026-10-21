---
name: aog-test-scenarios
description: Turn proposal section 8A functional test cases and ARD-TST-006 scenarios into OpenSpec scenarios and deterministic pytest cases with mock adapters. Use when writing specs, tasks, or tests for any AOG agent or the Controller workflow.
---

Sources: [proposal.md](../../../docs/proposal.md) section 8A (Test Cases 1–8 and "Conflicting Data"), ARD-TST-001..009 and ARD-TST-006 in [architecture-requirements.md](../../../docs/architecture-requirements.md).

## Steps
1. Read section 8A and ARD-TST-006; list each scenario with its expected outcome and the ARD IDs it exercises.
2. For OpenSpec specs, write each as WHEN/THEN scenarios citing ARD IDs. Cover normal, partial-data, failure, conflict, low-confidence, escalation, and human-approval cases for the capability.
3. For pytest, use deterministic mock adapters and fixed fixtures (ARD-TST-009, ARD-SYS-008); no network or real model calls in unit tests (stub the model boundary per ARD-TEC-005).
4. Required coverage groups:
   - Contracts: valid/invalid payload, schema rejection (ARD-TST-002).
   - Agent behavior: each specialist's deterministic checks and degraded modes (ARD-TST-003).
   - Controller: scoring, compliance gate, close-score (ARD-TST-004).
   - Human gate: nothing proceeds without approval, thresholds, conflict deferral (ARD-TST-005).
   - A2A: Maintenance<->M&L exchange recorded in case context.
   - Load redistribution and conflicting data (cases 6 and conflict scenario).
   - Security: prompt injection, read-only tools, no secret leakage (ARD-TST-007).
5. Add a requirement-to-test traceability entry (ARD-TST-001) for every scenario.

## Rule
Failures must assert a visible failure or escalation, never a success-shaped fallback.
