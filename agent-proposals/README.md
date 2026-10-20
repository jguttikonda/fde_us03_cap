# Agent Proposal Index

This folder contains the specialist agent proposals for the AOG Recovery Coordinator architecture.

## Root Proposal
- [../propsal.md](../propsal.md) — system-level architecture and controller-led orchestration design

## Shared Contract
- [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md) — canonical structure used by all agent proposals

## Specialist Agent Proposals
- [controller-agent-proposal.md](controller-agent-proposal.md) — workflow orchestration, coordination, and final synthesis
- [maintenance-agent-proposal.md](maintenance-agent-proposal.md) — technical repairability and maintenance feasibility
- [inventory-agent-proposal.md](inventory-agent-proposal.md) — material readiness, part availability, and sourcing
- [operations-agent-proposal.md](operations-agent-proposal.md) — route, fleet, and service disruption impact
- [report-creation-agent-proposal.md](report-creation-agent-proposal.md) — final recommendation package for human approval

## Coordination Model
The Controller Agent remains the orchestration layer, while each specialist agent owns its own local reasoning, context, memory, tool access, validation, and recommendation output. This separation preserves clarity and makes each agent easier to implement and govern.

## Standard Pattern for Each Agent
Each proposal follows the same contract format:

1. Purpose
2. Role in the System
3. Primary Responsibilities
4. Non-Deterministic Responsibilities
5. LLM Role
6. LLM Prompt Template
7. Expected Output Standard Format
8. Deterministic Responsibilities
9. LLM-Facing Inputs
10. Tool / External System Inputs
11. LLM-Facing Outputs
12. Tool / External System Outputs
13. Validation and Output Evaluation
14. Questions This Agent Seeks to Answer
15. Acceptance Criteria
16. Draft Notes

This ensures consistent implementation and easier maintenance across all proposals.
