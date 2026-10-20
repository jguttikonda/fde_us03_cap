# Maintenance Agent Proposal Draft

This document is a detailed draft for the Maintenance Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Maintenance Agent evaluates whether an aircraft can be recovered through technical repair and estimates the practical maintenance constraints involved in a recovery strategy.

## 2. Role in the System
This agent focuses on the technical feasibility of repair. It assesses the condition of the aircraft, identifies the maintenance work required, and determines whether the aircraft can realistically return to service within the required recovery window.

## 3. Primary Responsibilities
- Assess aircraft repairability
- Review maintenance history and current defects
- Estimate downtime and repair duration
- Identify technical dependencies and constraints
- Recommend repair versus defer or escalate

## 4. LLM Role
The Maintenance LLM acts as the technical feasibility analyst. It reads maintenance context, work orders, inspections, and engineering notes to reason about the most plausible repair path.

## 5. LLM Prompt Template
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Your job is to assess whether the aircraft can be repaired and determine the practical maintenance path required for recovery.

Inputs you must assess:
- Aircraft defect summary
- Maintenance records and prior inspections
- Work orders and repair tasks
- Part dependencies required for repair
- Technical constraints and assumptions

Decision rules:
- Evaluate the technical feasibility of repair.
- Identify required maintenance actions and dependencies.
- Highlight uncertainty, risks, and constraints.
- Recommend one of the following outcomes: repair, defer, escalate, or uncertain.
- State the confidence level and assumptions behind the decision.

Return only a structured technical recommendation with:
1. repairability status
2. required actions
3. estimated downtime
4. technical risk and assumptions
5. final recommendation
```

## 6. Expected Output Standard Format
```json
{
  "agent_name": "Maintenance Agent",
  "repairability_status": "feasible|uncertain|not_feasible",
  "summary": "Short technical assessment of the aircraft condition",
  "required_actions": [
    "Action 1",
    "Action 2"
  ],
  "estimated_ground_time_hours": 0,
  "technical_risks": [
    "Risk 1",
    "Risk 2"
  ],
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "recommendation": {
    "decision": "repair|defer|escalate|uncertain",
    "confidence": 0.0,
    "reasoning": "Why this recommendation is most credible",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 7. Deterministic Responsibilities
- Validate aircraft condition metadata and work-order completeness
- Check required maintenance actions against standard procedures
- Detect missing fields, incomplete records, or obvious data inconsistencies
- Apply safety and approval gates
- Map technical findings into structured repair categories

## 8. Non-Deterministic Responsibilities
- Interpret partial or ambiguous maintenance history
- Assess how uncertainty changes the repair recommendation
- Estimate turnaround based on incomplete operational realities
- Weigh technical feasibility against urgency and schedule pressure
- Recommend whether to repair, reroute, substitute, or escalate

## 9. LLM-Facing Inputs
These are the inputs the LLM should reason over to assess technical repairability:
- Aircraft defect summary and current technical status
- Maintenance history and prior inspections
- Work-order context and repair constraints
- Part dependency information relevant to the repair
- Technical notes, assumptions, and uncertainty in the aircraft record

## 10. Tool / External System Inputs
These are the structured system inputs consumed by the agent:
- Aircraft maintenance records and defect logs
- Work-order and task management systems
- Engineering and inspection APIs
- Parts dependency metadata from maintenance systems
- Safety and approval rule sources used for validation

## 11. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts:
- Repair feasibility assessment
- Estimated grounded time and technical downtime range
- Required maintenance actions and dependencies
- Technical risk and constraint summary
- Recommendation to repair, defer, or escalate

## 12. Tool / External System Outputs
These are the downstream system artifacts generated after reasoning:
- Structured maintenance recommendation payload
- Repair work package summary for operations and planning teams
- Technical risk flags for downstream systems
- Escalation or exception record when confidence is low
- Decision record used by the Controller for final synthesis

## 13. Validation and Output Evaluation
The Maintenance Agent should validate its output by checking:
- whether the evidence supports the repair conclusion
- whether the recommended actions are technically coherent
- whether there are hidden dependencies not captured in the current context
- whether the output is sufficiently explicit for downstream decision-making

## 14. Questions This Agent Seeks to Answer
- Is the aircraft repairable under the current conditions?
- How long will the repair take?
- What actions, parts, and expertise are required?
- Which technical constraints could prevent the repair path?
- What is the confidence level in this recommendation?

## 15. Acceptance Criteria
The Maintenance Agent is successful when it:
- makes a technically credible repair assessment
- clearly states assumptions and risk
- distinguishes between confirmed feasible and uncertain repair paths
- supports the Controller with actionable maintenance evidence

## 16. Draft Notes
This agent is the technical decision anchor for the aircraft recovery process. It should help determine whether a repair path is realistic, safe, and operationally defensible.
