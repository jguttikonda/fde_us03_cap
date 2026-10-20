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

## 4. Non-Deterministic Responsibilities
- Interpret partial or ambiguous maintenance history
- Assess how uncertainty changes the repair recommendation
- Estimate turnaround based on incomplete operational realities
- Weigh technical feasibility against urgency and schedule pressure
- Recommend whether to repair, reroute, substitute, or escalate

## 5. Context Engineering and Memory Management
The Maintenance Agent maintains a technical case memory focused on the active aircraft defect, maintenance state, work-order completeness, safety constraints, and repairability assumptions. It keeps the current evidence window compact and avoids long-term retention of noisy inspection records unless they directly affect the current recovery decision.

- Short-term memory: current aircraft condition, active defect summary, safety gate state, and work-order status
- Working memory: the technical findings, assumptions, and dependencies currently under consideration for repair feasibility
- Durable local memory: recurring maintenance patterns, standard rule exceptions, and known repair categories for similar defects
- Context compression rule: retain only the maintenance facts that materially affect the repair recommendation and downstream approvals

## 6. LLM Role
The Maintenance LLM acts as the technical feasibility analyst. It reads maintenance context, work orders, inspections, and engineering notes to reason about the most plausible repair path.

## 7. LLM Prompt Template
This agent should use a short sequence of prompt interactions instead of a single broad technical prompt. The split keeps fact extraction, reasoning, and final validation separate, which improves traceability and reduces context drift.

### 7.1 Prompt A — Maintenance Evidence Grounding
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Your task is to extract only the fact-backed maintenance evidence relevant to the current defect and repair decision.

Inputs you must assess:
- Aircraft defect summary
- Maintenance history and inspection data
- Work-order status and task details
- Known dependencies and technical constraints

Decision rules:
- Keep only facts that materially affect repairability
- Flag missing fields, stale records, or contradictory maintenance notes
- Do not infer technical feasibility without supporting evidence

Return only a structured output with:
1. evidence_summary
2. missing_data
3. assumptions
4. confidence_level
```

### 7.2 Prompt B — Technical Repair Reasoning
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Use the grounded evidence from Prompt A to assess repair feasibility and determine the likely maintenance path.

Inputs you must assess:
- Relevant aircraft condition facts
- Maintenance records and defect history
- Work-order completeness and technical constraints
- Part dependency requirements

Decision rules:
- Determine whether repair is feasible, uncertain, or not feasible
- Identify the maintenance actions and dependencies required
- Highlight risk and technical constraints clearly

Return only a structured output with:
1. repairability_status
2. required_actions
3. estimated_ground_time_hours
4. technical_risks
5. confidence
```

### 7.3 Prompt C — Final Validation and Output Normalization
```text
You are the Maintenance Agent for an aircraft AOG recovery workflow.

Review the repair recommendation and ensure it is consistent with safety constraints, procedure rules, and the agent’s domain boundaries.

Inputs you must assess:
- Repairability recommendation
- Safety gate state
- Required approvals and dependencies

Decision rules:
- Reject unsupported technical conclusions
- Ensure the output is traceable and ready for downstream use
- Normalize the result into the standard maintenance contract format

Return only a structured output with:
1. final_summary
2. final_recommendation
3. required_approvals
4. approval_status
```

## 8. Expected Output Standard Format
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

## 9. Deterministic Responsibilities
- Validate aircraft condition metadata and work-order completeness
- Check required maintenance actions against standard procedures
- Detect missing fields, incomplete records, or obvious data inconsistencies
- Apply safety and approval gates
- Map technical findings into structured repair categories

## 9A. Domain Validation and Conflict Handling
The Maintenance Agent must identify when the technical signal is not consistent enough to support a confident recommendation.

- If maintenance estimates a 3-hour repair but operations indicates a 7-hour disruption, the case is flagged as internally inconsistent
- If the defect summary is incomplete or work-order data is missing required fields, the recommendation should be provisional and escalated
- If safety or engineering approval is not present, the maintenance recommendation must remain advisory until approved

This ensures the Maintenance Agent contributes technically grounded evidence without overstating confidence.

### 8.1 MCP Configuration for Deterministic Validation
This agent uses MCP-hosted tools to perform the validation steps that are deterministic and repeatable. The purpose is to ensure the LLM only reasons over complete and trustworthy technical inputs.

- `validate_aircraft_metadata`: checks aircraft identity, defect status, and required maintenance context before analysis
- `validate_workorder_completeness`: verifies task records, required fields, and work-order linkage are present
- `check_standard_maintenance_rules`: applies maintenance procedure checks and rule-based repair mapping
- `check_safety_gate`: validates whether the technical path is compliant with configured safety restrictions and approval conditions
- `map_repair_category`: converts the technical findings into a standard repair classification used by downstream agents

### 8.2 Domain APIs Reached through MCP Tools
The deterministic validation layer calls the domain APIs that own the source technical facts:

- Aircraft Maintenance API: returns defect history, aircraft status, and technical metadata
- Work Order / Task API: returns repair tasks, work-order completeness, and required maintenance actions
- Engineering Rules API: provides standard procedures, maintenance constraints, and repair classification logic
- Safety / Approval API: enforces gate checks and returns compliance or exception states
- Part Dependency API: verifies which components and spare dependencies are required for the proposed repair path

### 8.3 Tool Interaction Contract (JSON)
Each tool call captures the exact request/response contract that feeds the deterministic repairability validation layer.

#### 8.3.1 `validate_aircraft_metadata`
Request JSON:
```json
{
  "aircraft_tail_number": "N123AB",
  "required_fields": ["aircraft_id", "status", "defect_summary", "maintenance_history"],
  "include_history": true
}
```

Response JSON:
```json
{
  "status": "validated",
  "aircraft_id": "N123AB",
  "current_status": "AOG",
  "missing_fields": [],
  "defect_summary": "Hydraulic leak",
  "maintenance_history_count": 7
}
```

#### 8.3.2 `validate_workorder_completeness`
Request JSON:
```json
{
  "aircraft_id": "N123AB",
  "work_order_id": "WO-44019",
  "required_sections": ["task_list", "part_dependencies", "inspection_notes"]
}
```

Response JSON:
```json
{
  "work_order_status": "complete",
  "missing_sections": [],
  "part_dependencies": ["hydraulic_pump", "seal_kit"],
  "inspection_notes_present": true
}
```

#### 8.3.3 `check_standard_maintenance_rules`
Request JSON:
```json
{
  "aircraft_type": "A320",
  "defect_code": "HYD-LEAK",
  "maintenance_context": {
    "station": "MIA",
    "mro_capability": "line-maintenance"
  }
}
```

Response JSON:
```json
{
  "rule_check": "passed",
  "repair_category": "line_repair_supported",
  "required_approvals": ["engineering_approval"],
  "warnings": []
}
```

#### 8.3.4 `check_safety_gate`
Request JSON:
```json
{
  "aircraft_id": "N123AB",
  "defect_code": "HYD-LEAK",
  "repair_plan": {
    "action": "replace_hydraulic_pump",
    "station": "MIA"
  },
  "safety_constraints": ["engineering_approval", "aircraft_grounding_check"]
}
```

Response JSON:
```json
{
  "safety_gate": "passed",
  "approval_required": true,
  "exceptions": [],
  "compliance_status": "ready_for_technical_review"
}
```

#### 8.3.5 `map_repair_category`
Request JSON:
```json
{
  "repair_findings": [
    "hydraulic_pump_failure",
    "seal_kit_required"
  ],
  "aircraft_type": "A320",
  "station_capability": "line-maintenance"
}
```

Response JSON:
```json
{
  "repair_category": "line_repair_supported",
  "ground_time_hours": 8,
  "category_reason": "defect is within line-maintenance capability and replacement parts are available",
  "classification_confidence": 0.91
}
```

## 10. LLM-Facing Inputs
These are the curated, validated facts the LLM should reason over to assess technical repairability. This is the cleaned evidence set produced by the deterministic checks and not a raw maintenance dump.
- Aircraft defect summary and current technical status
- Maintenance history and prior inspections
- Work-order context and repair constraints
- Part dependency information relevant to the repair
- Technical notes, assumptions, and uncertainty in the aircraft record

## 11. Tool / External System Inputs
This is the upstream evidence handshake: the structured system inputs consumed by the agent before the model reasons.
- Aircraft maintenance records and defect logs
- Work-order and task management systems
- Engineering and inspection APIs
- Parts dependency metadata from maintenance systems
- Safety and approval rule sources used for validation

## 12. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after evaluating the validated evidence:
- Repair feasibility assessment
- Estimated grounded time and technical downtime range
- Required maintenance actions and dependencies
- Technical risk and constraint summary
- Recommendation to repair, defer, or escalate

## 13. Tool / External System Outputs
This is the downstream execution handshake: the structured system artifacts generated after the accepted guidance is converted into machine-usable maintenance actions.
- Structured maintenance recommendation payload
- Repair work package summary for operations and planning teams
- Technical risk flags for downstream systems
- Escalation or exception record when confidence is low
- Decision record used by the Controller for final synthesis

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This flow ensures the technical decision is based on verified aircraft evidence and that the resulting maintenance recommendation is traceable to the same facts.

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
