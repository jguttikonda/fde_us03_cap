---
name: aog-agent-contract
description: Scaffold or validate an AOG agent spec/implementation against the 17-section agent contract (AGENT_CONTRACT_TEMPLATE.md). Use when creating or changing any agent proposal, OpenSpec capability spec for an agent, or its handshake/validation sections.
---

Keep agent definitions consistent with [AGENT_CONTRACT_TEMPLATE.md](../../../docs/agent-proposals/AGENT_CONTRACT_TEMPLATE.md) and the per-agent proposals in [docs/agent-proposals/](../../../docs/agent-proposals/README.md). The template is the source; do not restate it.

## Steps
1. Identify the agent (Controller, Maintenance, Materials & Logistics, Operations) and open its proposal.
2. Verify sections 1–17 exist in template order, including 2A (Agent type, Called by, Calls, Payload with handshake IDs) and 5 (context/memory: local scope, memory pattern, compression/retention).
3. Verify section 7 uses the bounded Prompt A (grounding) / B (reasoning) / C (validation) pattern rather than one large prompt.
4. Verify section 8 output carries evidence, missing data, assumptions, confidence, and a decision status, and that section 9 lists only deterministic rules.
5. Check consistency with the ARD IDs for the agent (CTL / MNT / MLG / OPS) and with proposal.md section 6.
6. Map each proposal section to an OpenSpec requirement or Pydantic contract so nothing is dropped (ARD-OSP-005).

## Output
List of missing/out-of-order sections, handshake mismatches between agents (e.g. Maintenance H3/H4 vs M&L), and fixes. Do not edit proposals unless asked.
