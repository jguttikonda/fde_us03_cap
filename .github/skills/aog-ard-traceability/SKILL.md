---
name: aog-ard-traceability
description: Generate or audit ARD Traceability and Rubric and Capability Coverage content for OpenSpec proposals, designs, specs, and tasks, as required by openspec/config.yaml. Use when drafting or verifying any OpenSpec change or before archive.
---

Implements the rules in [openspec/config.yaml](../../../openspec/config.yaml) against [docs/architecture-requirements.md](../../../docs/architecture-requirements.md) (ARD), [proposal.md](../../../docs/proposal.md), and [capstone_rubric_phase_checklist.md](../../../docs/capstone_rubric_phase_checklist.md).

## Steps
1. Determine the change scope (agent/capability). Select applicable ARD families: SYS, DAT, CTL, MNT, MLG, OPS, GOV, RES, SEC, OBS, NFR, TST, OSP, plus TEC/RUB/CAP where relevant.
2. **Proposal**: write an "ARD Traceability" section listing addressed, deferred, and out-of-scope IDs, each with rationale; and a "Rubric and Capability Coverage" section mapping rubric checkboxes and proposal capabilities to frameworks, retained evidence, verification, and human responsibilities. Declare any ARD deviation explicitly.
3. **Design**: explain how each applicable ID is satisfied; document component boundaries, typed contracts, deterministic controls, failure behavior, audit events, and human-approval enforcement; record trade-offs.
4. **Specs**: cite IDs in requirements/scenarios; include normal, partial-data, failure, conflict, low-confidence, escalation, and human-approval scenarios when applicable.
5. **Tasks**: each task cites the OpenSpec or ARD requirement, bundles implementation + focused tests + traceability updates, and includes verification tasks (deterministic rules, degraded behavior, security, auditability, human gate) and evidence tasks (RAPID, AI-assisted practice, sponsor demo).
6. **Audit mode**: flag missing IDs, silent requirement removal, unverified deferrals.

## Rule
Never present framework installation as evidence of behavior; evidence is retained, reviewable artifacts (ARD-TEC-019/020).
