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

## 4. Non-Deterministic Responsibilities
- Rank recovery options using incomplete or conflicting evidence
- Explain why one path is preferred over another
- Turn technical and operational trade-offs into business-readable guidance
- Present uncertainty, confidence, and assumptions clearly
- Recommend the final path while keeping the reasoning transparent

## 5. Context Engineering and Memory Management
The Report Creation Agent maintains a synthesis memory for the active case, including the accepted specialist findings, unresolved risks, approval requirements, and final narrative state. It retains only the evidence and decision context required to build a clear human-facing recommendation, while leaving raw source artifacts in the underlying domain systems.

- Short-term memory: active case summary, final recommendation inputs, and human-approval constraints
- Working memory: versioned synthesis state, uncertainties, and final trade-off narrative under construction
- Durable local memory: report formatting patterns, governance expectations, and recurring decision-summary structures
- Context compression rule: keep the evidence that matters for a defensible final recommendation and discard noisy intermediate details

## 6. LLM Role
The Report LLM acts as the synthesis and narrative layer. It transforms technical, material, and operational data into a clear recovery recommendation that is understandable to decision-makers.

## 7. LLM Prompt Template
This agent should use a multi-stage prompt flow instead of a single narrative synthesis prompt. A sequence of narrower prompts improves evidence fidelity, reduces hallucination risk, and ensures the final report is valid before human review.

### 7.1 Prompt A — Case Synthesis and Evidence Grounding
```text
You are the Report Creation Agent for an aircraft AOG recovery workflow.

Your task is to extract the decision-relevant evidence from the specialist outputs without inventing missing facts.

Inputs you must assess:
- Maintenance feasibility output
- Inventory readiness output
- Operations impact assessment
- Controller coordination summary

Decision rules:
- Keep only facts that support the final decision brief
- Flag contradictions, missing specialist input, or low-confidence findings
- Do not assume a recommendation without traceable evidence

Return only a structured output with:
1. evidence_summary
2. missing_data
3. contradictions
4. confidence_level
```

### 7.2 Prompt B — Trade-Off and Recommendation Reasoning
```text
You are the Report Creation Agent for an aircraft AOG recovery workflow.

Use the grounded evidence from Prompt A to rank the viable recovery options and justify the preferred recommendation.

Inputs you must assess:
- Specialist findings and confidence states
- Business and operational trade-offs
- Human approval constraints and escalation thresholds

Decision rules:
- Rank all viable options by combined evidence and risk
- Explain assumptions and trade-offs clearly
- Recommend the option that best balances feasibility, readiness, and disruption

Return only a structured output with:
1. ranked_options
2. trade_offs
3. risks_and_assumptions
4. recommendation
5. confidence
```

### 7.3 Prompt C — Human-Approval Finalization
```text
You are the Report Creation Agent for an aircraft AOG recovery workflow.

Review the final decision brief and make sure it is clear, reviewable, and suitable for human approval.

Inputs you must assess:
- Final recommendation
- Governance and approval requirements
- Remaining uncertainty and escalation triggers

Decision rules:
- Ensure the final brief is concise and decision-ready
- Preserve uncertainty where it matters
- Normalize the output into the final approval package format

Return only a structured output with:
1. final_summary
2. approval_action
3. remaining_risks
4. approval_status
```

## 8. Expected Output Standard Format
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

## 9. Deterministic Responsibilities
- Validate that all required inputs are present
- Apply the standard report template
- Check the integrity of the final recommendation structure
- Identify missing or contradictory information
- Standardize the final output format for approval workflows

### 8.1 MCP Configuration for Deterministic Validation
The Report Creation Agent uses deterministic MCP tools to verify that every required recommendation input is complete before the model synthesizes the final narrative.

- `validate_input_package`: confirms all specialist outputs are present, complete, and in the expected schema
- `check_template_rules`: applies the approved decision-brief structure and required sections
- `check_missing_findings`: flags contradictions, missing evidence, or incomplete reasoning blocks
- `verify_output_schema`: ensures the final recommendation payload conforms to the downstream approval format
- `prepare_approval_package`: transforms the validated final report into the structured artifact used by human reviewers

### 8.2 Domain APIs Reached through MCP Tools
These deterministic checks depend on APIs that manage the reporting and governance layer:

- Specialist Output API: collects validated findings from Maintenance, Inventory, and Operations agents
- Reporting Template API: returns the approved final briefing structure and required fields
- Governance / Policy API: enforces report completeness, approval requirements, and review rules
- Audit / Decision Log API: stores the final recommendation, assumptions, and context for traceability
- Human Approval Workflow API: prepares the final brief in the format required for approval or escalation

### 8.3 Tool Interaction Contract (JSON)
The output of the deterministic validation layer is a fully structured brief, ready to be interpreted by the synthesis LLM and passed to the human approver.

#### 8.3.1 `validate_input_package`
Request JSON:
```json
{
  "agent_outputs": {
    "maintenance": "...",
    "inventory": "...",
    "operations": "..."
  },
  "required_fields": ["summary", "recommendation", "risk_factors"]
}
```

Response JSON:
```json
{
  "validation_status": "passed",
  "missing_fields": [],
  "incomplete_agents": [],
  "all_inputs_ready": true
}
```

#### 8.3.2 `check_template_rules`
Request JSON:
```json
{
  "template_name": "aog_final_brief",
  "required_sections": ["summary", "ranked_options", "trade_offs", "approval_action"]
}
```

Response JSON:
```json
{
  "template_status": "valid",
  "required_sections_present": true,
  "schema_version": "v1"
}
```

#### 8.3.3 `prepare_approval_package`
Request JSON:
```json
{
  "decision_summary": "Recommended repair with alternate parts and return to service within 12 hours",
  "final_recommendation": "repair",
  "approval_required": true,
  "human_reviewer": "ops_lead"
}
```

Response JSON:
```json
{
  "approval_package_id": "APR-7781",
  "status": "ready_for_review",
  "approval_route": "ops_lead",
  "stored_in_audit_log": true
}
```

#### 8.3.4 `check_missing_findings`
Request JSON:
```json
{
  "agent_outputs": {
    "maintenance": "repair feasible",
    "inventory": "part available with delay",
    "operations": "critical customer impact"
  },
  "required_fields": ["summary", "recommendation", "risk_factors"]
}
```

Response JSON:
```json
{
  "missing_findings": [],
  "contradictions": [],
  "status": "complete",
  "risk_note": "customer impact remains high but repair path remains feasible"
}
```

#### 8.3.5 `verify_output_schema`
Request JSON:
```json
{
  "draft_report": {
    "summary": "Repair path recommended",
    "ranked_options": [{ "rank": 1, "option": "repair" }],
    "trade_offs": ["part lead time", "customer delay"],
    "approval_action": "approve"
  },
  "schema_version": "v1"
}
```

Response JSON:
```json
{
  "schema_status": "valid",
  "missing_sections": [],
  "validation_passed": true,
  "approved_for_human_review": true
}
```

## 9. LLM-Facing Inputs
These are the curated, validated facts the LLM should reason over to assemble the final recommendation. This is the synthesized decision context drawn from the specialist outputs and governance constraints.
- Maintenance feasibility output
- Inventory readiness and sourcing results
- Operations impact and disruption assessment
- Controller coordination summary and case context
- Human approval thresholds, risk posture, and decision constraints

## 10. Tool / External System Inputs
This is the upstream evidence handshake: the structured system inputs consumed by the agent before the final synthesis occurs.
- Specialist agent output payloads
- Shared coordination context from the Controller
- Reporting templates and governance rules
- Human approval workflow metadata
- Decision support or audit system integration data

## 11. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts after evaluating the assembled evidence:
- Final recommendation narrative
- Ranked recovery options with trade-offs
- Risk and assumption summary
- Decision-ready brief for human approval
- Escalation note if no option is clearly preferred

## 12. Tool / External System Outputs
This is the downstream execution handshake: the final structured package generated after the accepted recommendation is written into the system for human or downstream action.
- Final human-readable recommendation package
- Approval-ready brief for operations leadership
- Decision record stored with supporting evidence
- Escalation or exception event if confidence is low
- Archived rationale for audit and later review

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This ensures the final decision brief remains grounded in the real evidence produced by the earlier agents and is then stored as a reviewable system artifact.

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
