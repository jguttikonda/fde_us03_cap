# AGENTS.md

Project guidance for AI coding agents (ARD-TEC-016). The full rule set lives in [.github/copilot-instructions.md](.github/copilot-instructions.md); read it first.

## Sources of truth
- [docs/architecture-requirements.md](docs/architecture-requirements.md) — ARD, normative
- [docs/proposal.md](docs/proposal.md) and [docs/agent-proposals/](docs/agent-proposals/README.md)
- [openspec/config.yaml](openspec/config.yaml) — rules for proposal, design, specs, tasks, apply, archive

## Agent boundaries
| Agent | Proposal | Owns |
|---|---|---|
| Controller | `controller-agent-proposal.md` | intake, routing, conflict detection, compliance gate, scoring, decision brief, approval handoff |
| Maintenance | `maintenance-agent-proposal.md` | repairability, ground time, recurring failure, airworthiness/engineering gate |
| Materials & Logistics | `materials-logistics-agent-proposal.md` | inventory, alternates, part authorization/traceability, sourcing, ETA, cost |
| Operations | `operations-agent-proposal.md` | route/fleet/service impact, package load redistribution |

Maintenance and Materials & Logistics are A2A peers. Specialists never rank options and never approve; the Controller ranks; humans decide.

## Rules
- Advisory only. No operational action is ever executed by an agent.
- Cite ARD IDs in code docstrings/tests, specs, tasks, and design.
- Stop and report when a request conflicts with the ARD.
- Do not hide degraded evidence; do not add fallbacks that look like success.

## Commands
- Workflow: `/opsx-explore`, `/opsx-propose`, `/opsx-new`, `/opsx-continue`, `/opsx-ff`, `/opsx-apply`, `/opsx-verify`, `/opsx-archive`
- Dev agents: `.github/agents/aog-*.agent.md`; skills: `.github/skills/aog-*/SKILL.md`
- Verify: Ruff, type checks, pytest with coverage (ARD-TEC-008/009/017)
