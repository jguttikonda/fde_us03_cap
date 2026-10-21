# Agent Proposal Index

This folder contains the agent proposals for the AOG Recovery Coordinator architecture: four agents in total (Controller Agent (Recovery Coordinator), Maintenance Agent, Materials & Logistics Agent, and Operations Agent).

## Root Proposal
- [../proposal.md](../proposal.md) — system-level architecture and controller-led orchestration design

## Shared Contract
- [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md) — canonical structure used by all agent proposals

## Coordinator
- [controller-agent-proposal.md](controller-agent-proposal.md) — workflow orchestration, coordination, deterministic final report assembly, and human approval handoff

## Specialist Agent Proposals
- [maintenance-agent-proposal.md](maintenance-agent-proposal.md) — technical repairability and maintenance feasibility
- [materials-logistics-agent-proposal.md](materials-logistics-agent-proposal.md) — peer of Maintenance (A2A): inventory, alternate parts, transfer and vendor sourcing, shipping, and ETA
- [operations-agent-proposal.md](operations-agent-proposal.md) — route, fleet, and service disruption impact

## Coordination Model
The Maintenance Agent and Materials & Logistics Agent collaborate directly as peers (A2A), with every exchange recorded in the Controller case context. The Controller Agent remains the orchestration layer, while each specialist agent owns its own local reasoning, context, memory, tool access, validation, and recommendation output. This separation preserves clarity and makes each agent easier to implement and govern.

The merged design also incorporates the decision-scoring and confidence model from the parallel Unit B proposal: each domain agent contributes evidence, the Controller Agent ranks viable options using a deterministic rule, and a final recommendation is only accepted when the confidence, assumptions, and risk profile are explicit and reviewable by a human approver.

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
