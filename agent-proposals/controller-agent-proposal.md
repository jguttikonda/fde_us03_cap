# Controller Agent Proposal Draft

This document is a detailed draft for the Controller Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Controller Agent is the orchestration layer for the AOG recovery workflow. It receives the incoming aircraft ground event, determines which specialist agents are required, coordinates the information flow, and produces the final recommendation for human approval.

## 2. Role in the System
The Controller Agent is not a domain specialist. It is the workflow director that:
- validates the event and scope
- routes the case to the relevant agents
- aggregates intermediate outcomes
- resolves conflicts across specialist recommendations
- produces the final decision package for the human approver

## 3. Primary Responsibilities
- Event intake and validation
- Case triage and routing
- Shared context management
- Coordination across the maintenance, inventory, and operations branches
- Final recommendation synthesis
- Human handoff and escalation logic

## 4. LLM Role
The Controller LLM acts as the coordination planner. It should not own every technical detail from each specialist domain. Instead, it reasons over the shared state and decides what matters most for the current AOG decision.

## 5. LLM Prompt Template
```text
You are the Controller Agent for an aircraft AOG recovery workflow.

Your task is to coordinate the incident response by evaluating the current AOG case, selecting the required specialist agents, and synthesizing a final recommendation for human approval.

Inputs you must consider:
- AOG event summary
- Aircraft technical context
- Maintenance findings
- Inventory readiness findings
- Operations impact analysis
- Human approval constraints

Decision rules:
- Identify the actual decision problem and required analysis scope.
- Prioritize the most relevant specialist outputs.
- Resolve contradictions or missing data before finalizing the recommendation.
- Recommend the best recovery path with rationale, confidence, and key risks.
- Keep the recommendation explainable and reviewable by a human approver.

Return only a structured decision summary with:
1. case status
2. relevant specialist findings
3. recommended recovery path
4. confidence level
5. key assumptions and risks
6. next action for human approval
```

## 6. Expected Output Standard Format
```json
{
  "agent_name": "Controller Agent",
  "case_status": "active|resolved|escalated",
  "summary": "Short narrative of the current AOG decision context",
  "relevant_agents": ["Maintenance Agent", "Inventory Agent", "Operations Agent"],
  "key_findings": [
    "Finding 1",
    "Finding 2"
  ],
  "recommended_recovery_path": {
    "option": "repair|substitute|transfer|delay|escalate",
    "confidence": 0.0,
    "rationale": "Why this option is preferred",
    "assumptions": ["Assumption 1", "Assumption 2"],
    "risks": ["Risk 1", "Risk 2"]
  },
  "human_approval_required": true,
  "next_action": "What the human decision-maker should do next"
}
```

## 7. Deterministic Responsibilities
- Validate that an AOG event contains the required fields
- Check whether required data sources are available
- Apply workflow routing rules
- Enforce escalation thresholds and approval gates
- Standardize output schema and final summary structure

## 8. Non-Deterministic Responsibilities
- Interpret incomplete or conflicting signals across domains
- Decide which agent output is most influential for this case
- Prioritize the response path when multiple valid options exist
- Combine technical, material, and operational findings into a coherent recommendation
- Explain uncertainty and confidence when the decision is not fully deterministic

## 9. LLM-Facing Inputs
These are the inputs the LLM should reason over to make coordination decisions:
- AOG event details and recovery objective
- Aircraft status and current maintenance context
- Inventory availability and readiness signals
- Operational disruption and schedule impact summaries
- Inter-agent findings and unresolved contradictions
- Human approval constraints and escalation policy

## 10. Tool / External System Inputs
These are the structured inputs the agent receives from MCP tools or system integrations:
- Event payload from operations or monitoring systems
- Maintenance work-order and aircraft status APIs
- Inventory service data for parts and stock status
- Flight schedule and fleet disruption feeds
- Audit, approval, or governance system metadata

## 11. LLM-Facing Outputs
These are the outputs the LLM should produce as final reasoning and recommendation artifacts:
- Routing plan for the active AOG case
- Consolidated interpretation of specialist outputs
- Ranked recovery options with confidence and rationale
- Final recommendation package for human approval
- Flags for ambiguity, risk, and required escalation

## 12. Tool / External System Outputs
These are the downstream system artifacts generated after reasoning:
- Structured case status updates
- Coordinator summary payload passed to downstream services
- Human review package or decision brief
- Approval workflow trigger and escalation actions
- Audit record of reasoning, data sources, and final recommendation

## 13. Validation and Output Evaluation
Before sending the final recommendation downstream, the Controller should evaluate:
- completeness of specialist inputs
- consistency across specialist outputs
- missing assumptions or contradictions
- confidence level of the recommended path
- readability and traceability of the final report

## 14. Questions This Agent Seeks to Answer
- What is the real decision problem in this AOG case?
- Which specialist agents are relevant?
- Which findings should be considered high priority?
- What is the best-recommended recovery path?
- What should be presented to the human approver for final decision-making?

## 15. Acceptance Criteria
The Controller Agent is successful when it:
- routes the case correctly
- preserves shared context across agents
- brings together the right domain outputs
- produces a recommendation that is explainable and reviewable
- supports human approval rather than bypassing it

## 16. Draft Notes
This agent is the coordination layer, not the technical decision-maker. Its core value is structured orchestration, effective synthesis, and clear reporting.
