# Report Creation Agent Proposal Draft

This document is a detailed draft for the Report Creation Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Report Creation Agent synthesizes outputs from the other agents and produces the final recovery recommendation package for human review and approval.

## 2. Role in the System
This agent acts as the communication and decision synthesis layer. It aggregates evidence, clarifies trade-offs, and communicates the recommended path in a format suitable for human decision-makers.

## 3. Primary Responsibilities
- Consolidate specialist outputs
- Compare feasible recovery options
- Highlight trade-offs, assumptions, and risks
- Produce a final recommendation summary
- Prepare the decision package for human approval

## 4. LLM Role
The Report LLM acts as the synthesis and narrative layer. It transforms technical, material, and operational data into a clear recovery recommendation that is understandable to decision-makers.

## 5. LLM Prompt Template
```text
You are the Report Creation Agent for an aircraft AOG recovery workflow.

Your task is to consolidate the findings from Maintenance, Inventory, and Operations into a single decision-ready summary for human review.

Inputs you must assess:
- Maintenance feasibility output
- Inventory readiness output
- Operations impact assessment
- Shared coordination context from the Controller
- Risk posture and human approval requirements

Decision rules:
- Rank all viable recovery options based on combined evidence.
- Highlight trade-offs, assumptions, uncertainty, and risk.
- Recommend the best path for human approval.
- Keep the final report clear, concise, and operationally actionable.
- If ambiguity remains, state the unresolved issue and suggest escalation.

Return only a structured final decision brief with:
1. recommendation summary
2. ranked options
3. trade-off analysis
4. risks and assumptions
5. final approval action
```

## 6. Expected Output Standard Format
```json
{
  "agent_name": "Report Creation Agent",
  "decision_status": "recommended|requires_escalation|uncertain",
  "summary": "Short summary of the final recommended recovery path",
  "ranked_options": [
    {
      "rank": 1,
      "option": "repair|substitute|transfer|delay",
      "confidence": 0.0,
      "rationale": "Why this option ranks at this position"
    }
  ],
  "trade_offs": [
    "Trade-off 1",
    "Trade-off 2"
  ],
  "risks_and_assumptions": [
    "Risk or assumption 1",
    "Risk or assumption 2"
  ],
  "human_approval_action": "Approve / escalate / request more data",
  "final_recommendation": "Concise final decision narrative"
}
```

## 7. Deterministic Responsibilities
- Validate that all required inputs are present
- Apply the standard report template
- Check the integrity of the final recommendation structure
- Identify missing or contradictory information
- Standardize the final output format for approval workflows

## 8. Non-Deterministic Responsibilities
- Rank recovery options using incomplete or conflicting evidence
- Explain why one path is preferred over another
- Turn technical and operational trade-offs into business-readable guidance
- Present uncertainty, confidence, and assumptions clearly
- Recommend the final path while keeping the reasoning transparent

## 9. LLM-Facing Inputs
These are the inputs the LLM should reason over to assemble the final recommendation:
- Maintenance feasibility output
- Inventory readiness and sourcing results
- Operations impact and disruption assessment
- Controller coordination summary and case context
- Human approval thresholds, risk posture, and decision constraints

## 10. Tool / External System Inputs
These are the structured system inputs consumed by the agent:
- Specialist agent output payloads
- Shared coordination context from the Controller
- Reporting templates and governance rules
- Human approval workflow metadata
- Decision support or audit system integration data

## 11. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts:
- Final recommendation narrative
- Ranked recovery options with trade-offs
- Risk and assumption summary
- Decision-ready brief for human approval
- Escalation note if no option is clearly preferred

## 12. Tool / External System Outputs
These are the downstream system artifacts generated after reasoning:
- Final human-readable recommendation package
- Approval-ready brief for operations leadership
- Decision record stored with supporting evidence
- Escalation or exception event if confidence is low
- Archived rationale for audit and later review

## 13. Validation and Output Evaluation
The Report Creation Agent should confirm:
- whether all findings are represented in the final report
- whether the recommendation is internally consistent
- whether assumptions are clearly disclosed
- whether the human decision-maker can understand and act on the recommendation

## 14. Questions This Agent Seeks to Answer
- Which recovery options are feasible?
- What are the trade-offs among repair, substitution, and delay?
- Which option best balances technical feasibility, material readiness, and operational impact?
- How should this recommendation be explained clearly to a human approver?
- What risks and assumptions must be emphasized before approval?

## 15. Acceptance Criteria
The Report Creation Agent is successful when it:
- produces a clear and structured final recommendation
- explains trade-offs and uncertainty honestly
- supports human approval without hiding ambiguity
- turns multi-agent findings into a decision-ready brief

## 16. Draft Notes
This agent is the final decision support interface. It converts the system’s internal reasoning into a concise, explainable, and operationally actionable recommendation.
