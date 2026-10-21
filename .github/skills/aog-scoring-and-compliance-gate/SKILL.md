---
name: aog-scoring-and-compliance-gate
description: Specify, implement, or test the Controller's deterministic compliance gate and weighted option ranking (30/30/30/10, close-score rule, cost model, ranked alternatives). Use for any work on option scoring or recommendation ranking.
---

Source of truth: ARD-CTL-011..019 in [architecture-requirements.md](../../../docs/architecture-requirements.md) and [controller-agent-proposal.md](../../../docs/agent-proposals/controller-agent-proposal.md) (sections 9, 9A–9C).

## Rules
1. **Gate first** (ARD-CTL-017): exclude options failing airworthiness/engineering approval (Maintenance) or part authorization/traceability (M&L). List exclusions with reasons; never rank them.
2. **Candidates** (ARD-CTL-018): original part, preferred/alternate part, aircraft swap, flight delay; each with a sourcing method and a load-redistribution plan. Maintenance and M&L run concurrently per candidate, then Operations, then ranking.
3. **Weights** (ARD-CTL-011): speed 30, operational+package impact 30, risk 30, cost 10 (single `estimated_cost` USD per ARD-CTL-019).
4. **Deterministic** (ARD-CTL-012): pure functions, fixed normalization, no LLM arithmetic, no randomness; same input gives the same output.
5. **Transparency** (ARD-CTL-013/014): output factor scores, weights, aggregate, dominant evidence, assumptions, uncertainty, and ranked alternatives with trade-offs.
6. **Close score** (ARD-CTL-015): top options within 2 percentage points are presented together and require human selection.
7. Confidence and escalation follow ARD-GOV-001..005; the result is always a recommendation for human approval.

## Test checklist (ARD-TST-004, proposal cases 7 and 8)
- Excluded option never appears in ranking.
- Weight changes only through configuration, with tests proving the 30/30/30/10 baseline.
- Boundary cases: exactly 2 points apart, ties, single viable option, zero viable options (escalate, don't fabricate).
- Cost can flip a ranking only when other factors are close.
- Reproducibility across runs.
