# Copilot Instructions — AOG Recovery Coordinator

Satisfies ARD-TEC-016. Authoritative sources, in order of precedence:

1. [docs/architecture-requirements.md](../docs/architecture-requirements.md) (ARD) — normative engineering baseline
2. [docs/proposal.md](../docs/proposal.md) — system proposal
3. [docs/agent-proposals/](../docs/agent-proposals/README.md) — per-agent contracts (shape: `AGENT_CONTRACT_TEMPLATE.md`)
4. [openspec/config.yaml](../openspec/config.yaml) — artifact rules

If code or an artifact would contradict the ARD, stop and surface the conflict (ARD-OSP-005, `openspec/config.yaml` apply guidance). Never silently weaken it.

## System
Advisory-only AOG decision support. Four agents: **Controller** (orchestrator, scorer, recommendation owner — there is no separate Recommendation agent, ADR-001), **Maintenance**, **Materials & Logistics**, **Operations**. Maintenance <-> Materials & Logistics collaborate as A2A peers; every exchange is recorded in the Controller case context.

## Non-negotiable rules
- Humans approve every operational decision (ARD-PRN-001/002, ARD-GOV-006/008). No agent executes an operational action; no confidence score, test mode, or degraded mode bypasses approval.
- Compliance gate runs before scoring (ARD-CTL-017); excluded options are listed with reasons and never ranked.
- Score: speed 30 / ops+package impact 30 / risk 30 / cost 10, deterministic and independently testable (ARD-CTL-011..015). Top options within 2 points are presented for human selection.
- Confidence: >=0.70 preferred path, 0.50–0.69 provisional, <0.50 escalate; conflicting evidence defers approval (ARD-GOV-001..005).
- Missing, stale, conflicting, or unavailable evidence stays visible and lowers confidence or escalates. No success-shaped fallbacks (ARD-PRN-006, ARD-RES-006).
- Deterministic logic owns rules and arithmetic; LLMs own bounded judgment only (ARD-PRN-003/004).

## Stack and conventions
Python, Pydantic contracts at every boundary, Google ADK, typed tool adapters with deterministic local/mock integrations, typed settings, pytest, Ruff (ARD-TEC-001..009). Read-only tools by default, allowlisted (ARD-SEC-001..003). No committed secrets; no sensitive data in logs.

## OpenSpec workflow
explore -> propose/new -> continue/ff -> apply -> verify -> archive (`/opsx-*` prompts, `openspec-*` skills). Every proposal, design, spec, and task cites ARD IDs and includes the traceability sections required by `openspec/config.yaml`. Tests accompany implementation in the same change.

## Project agents and skills
- Agents: `.github/agents/` (`aog-controller-dev`, `aog-maintenance-dev`, `aog-materials-logistics-dev`, `aog-operations-dev`, `aog-ard-reviewer`). These are development-time helpers; they are distinct from the runtime ADK agents.
- Skills: `aog-agent-contract`, `aog-ard-traceability`, `aog-scoring-and-compliance-gate`, `aog-test-scenarios`, `aog-human-gate-check` in `.github/skills/`.
- Agents reference proposals; they do not copy prompt templates. The proposals remain the single source.

## Evidence
Frameworks and automation support but never replace peer review, human approval, Go/No-Go, or sponsor communication (ARD-TEC-020). Retain rubric/RAPID/AI-assistance evidence as repository artifacts (ARD-TEC-019).
