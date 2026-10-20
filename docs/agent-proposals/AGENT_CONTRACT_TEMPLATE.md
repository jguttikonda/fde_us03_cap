# Agent Contract Template

This document is the canonical template for all specialist agent proposals in the AOG Recovery Coordinator design.

Use this as the standard contract for every agent draft.

## Shared Structure
Every proposal must include the following sections in order:

1. Purpose
2. Role in the System
3. Primary Responsibilities
4. Non-Deterministic Responsibilities
5. Context Engineering and Memory Management
6. LLM Role
7. LLM Prompt Template
8. Expected Output Standard Format
9. Deterministic Responsibilities
10. LLM-Facing Inputs
11. Tool / External System Inputs
12. LLM-Facing Outputs
13. Tool / External System Outputs
14. Validation and Output Evaluation
15. Questions This Agent Seeks to Answer
16. Acceptance Criteria
17. Draft Notes

## Canonical Contract
```md
# [Agent Name] Proposal Draft

This document is a detailed draft for the [Agent Name] and supplements the root system proposal in ../propsal.md.

## 1. Purpose
Describe the specific objective of the agent.

## 2. Role in the System
Explain where the agent sits in the overall workflow and how it contributes to the recovery process.

## 3. Primary Responsibilities
List the domain-specific responsibilities of the agent.

## 4. Non-Deterministic Responsibilities
Describe how the agent reasons under ambiguity, partial evidence, and conflicting signals.

## 5. Context Engineering and Memory Management
Define how the agent manages its own local context window, working memory, and evidence retention within its domain scope. This section must clearly state what the agent keeps in short-term memory, what is summarized or compressed, what is discarded, and what remains as durable case memory for the current AOG event.

### 5.1 Local Context Scope
- Current aircraft case, domain facts, and active decision thread
- Relevant working assumptions, missing-data markers, and confidence state
- The evidence and constraints that influence this agent’s recommendation

### 5.2 Memory Pattern
- Short-term memory: the current case, active facts, pending decisions, and unresolved constraints
- Working memory: extracted evidence that the agent is using for current reasoning
- Durable local memory: policy rules, known exception patterns, and case-relevant learned guidance within this agent’s domain

### 5.3 Context Compression and Retention Rules
- Preserve source-backed facts and decisions; avoid storing raw noisy feeds without provenance
- Keep only the minimum signals required for decision quality and downstream coordination
- Record uncertainty, assumptions, and missing data explicitly so the model does not silently invent context
- Share only the compact, policy-safe summary needed by the Controller or other agents

## 6. LLM Role
Define the reasoned behavior expected from the model and what it should not own.

## 7. LLM Prompt Template
This agent should not rely on a single large prompt. It is better to split the model interaction into a small sequence of bounded prompts so each stage is responsible for a single job: evidence grounding, reasoning, and final validation.

### 7.1 Prompt A — Context Grounding and Evidence Extraction
```text
You are the [Agent Name] for an aircraft AOG recovery workflow.

Your task is to extract the fact-backed, case-relevant evidence from the current context.

Inputs you must assess:
- Source-backed case facts
- Structured system inputs
- Known exclusions or missing data flags

Decision rules:
- Keep only facts that materially affect this case
- Flag uncertainty, missing fields, or stale data
- Do not invent conclusions from incomplete information

Return only a structured output with:
1. evidence_summary
2. missing_data
3. assumptions
4. confidence_level
```

### 7.2 Prompt B — Domain Reasoning and Recommendation
```text
You are the [Agent Name] for an aircraft AOG recovery workflow.

Use the validated evidence from Prompt A and reason only within your domain scope.

Inputs you must assess:
- Relevant case facts
- Applicable policy, constraints, and thresholds
- Current uncertainty and assumptions

Decision rules:
- Evaluate the most likely domain outcome
- Distinguish between confirmed fact and inference
- Recommend the best action supported by the evidence

Return only a structured output with:
1. findings
2. decision
3. rationale
4. risk_flags
5. confidence
```

### 7.3 Prompt C — Final Validation and Output Normalization
```text
You are the [Agent Name] for an aircraft AOG recovery workflow.

Review the reasoning from Prompt B and confirm the result aligns with schema, policy, and the agent’s responsibility boundaries.

Inputs you must assess:
- Domain recommendation
- Policy and safety constraints
- Required downstream actions

Decision rules:
- Ensure the output is grounded in evidence
- Reject unsupported claims or hidden assumptions
- Normalize the final answer into the standard agent contract format

Return only a structured output with:
1. final_summary
2. final_decision
3. next_action
4. approval_status
```

## 8. Expected Output Standard Format
```json
{
  "agent_name": "[Agent Name]",
  "status": "active|resolved|uncertain",
  "summary": "Short summary",
  "key_findings": ["Finding 1"],
  "recommendation": {
    "decision": "repair|delay|escalate|source|reroute|approve",
    "confidence": 0.0,
    "reasoning": "Why this recommendation is preferred",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 9. Deterministic Responsibilities
- Validate required structured inputs
- Apply known policy, thresholds, and route rules
- Detect missing data and enforce standard validation checks

### 8.1 MCP Configuration for Deterministic Validation
Describe the MCP tool layer used to enforce the deterministic checks before the LLM reasons over the case.

- Tool A: validates required data and schema checks
- Tool B: applies domain policy and route rules
- Tool C: enforces escalation and governance boundaries

### 8.2 Domain APIs Reached through MCP Tools
List the APIs behind the deterministic tools and indicate which domain systems they belong to.

- Domain API 1: validates structured facts and metadata
- Domain API 2: enforces business rules, safety gates, or policy checks
- Domain API 3: returns required state or workflow data for decision support

### 8.3 Tool Interaction Contract (JSON)
Describe the exact request and response JSON shape exchanged between each MCP tool and the underlying domain API.

#### 8.3.1 `tool_name_1`
Request JSON:
```json
{
  "example_field": "example_value"
}
```

Response JSON:
```json
{
  "status": "validated",
  "result": "example_result"
}
```

#### 8.3.2 `tool_name_2`
Request JSON:
```json
{
  "example_field": "example_value"
}
```

Response JSON:
```json
{
  "status": "passed",
  "result": "example_result"
}
```

## 9. LLM-Facing Inputs
The LLM should receive only the curated, validated, and relevant facts required to reason. This section is the human-readable or structured interpretation of the underlying system truth, not a copy of raw API payloads.

- Inputs the model should reason over as narrative or structured context
- Only trusted, filtered facts from the deterministic layer
- Ambiguities, assumptions, and missing-data markers that matter to the decision

## 10. Tool / External System Inputs
This is the upstream system handshake: structured facts, records, and policy data gathered through MCP tools and domain APIs before the model reasons. These inputs become the authoritative evidence set for the LLM-facing view.

- Structured system data from MCP tools, APIs, and operational feeds
- Validated event records, rule outputs, and state snapshots
- Inputs that are transformed or summarized into the LLM-facing context

## 11. LLM-Facing Outputs
This is the model’s internal reasoning contract: the summary, decision, confidence, required facts, and follow-up actions produced for coordination, human review, and downstream system action.

- Outputs the model should produce for coordination and human review
- Decision rationale, uncertainty, and required follow-up actions
- The bridge between evidence-based reasoning and actionable system output

## 12. Tool / External System Outputs
This is the downstream handshake: the structured result generated after the LLM recommendation is accepted and converted into records, tasks, or system actions. It must be machine-usable and traceable back to the LLM decision.

- Structured downstream artifacts, tasks, or records created after reasoning
- System-level outputs that can be passed to the Controller or external APIs
- Traceable evidence package for audit, compliance, and execution

### Handshake Chain
Tool / External System Inputs (10) -> LLM-Facing Inputs (9) -> LLM-Facing Outputs (11) -> Tool / External System Outputs (12)

This sequence ensures the model never reasons over unvalidated raw data, and every downstream action remains grounded in a traceable evidence chain.

## 13. Validation and Output Evaluation
- Validate completeness, consistency, and obvious gaps
- Check whether the result is grounded in evidence and ready for downstream use

## 14. Questions This Agent Seeks to Answer
- What problem is this agent solving?
- Which route or action is most appropriate?
- What assumptions and unknowns remain?

## 15. Acceptance Criteria
- The agent provides a credible and explainable recommendation
- It distinguishes between confirmed fact and uncertainty
- It supports downstream coordination and human approval

## 16. Draft Notes
Add implementation or design notes relevant to the agent.
```

## Rules for All Agent Drafts
- Keep the same structure across all agents.
- Do not rename the sections.
- Keep deterministic and non-deterministic responsibilities explicit.
- Separate LLM reasoning inputs/outputs from tool and API inputs/outputs.
- Include both validation logic and decision logic.
- Ensure each agent produces a structured decision artifact for the Controller or for human review.

## Why this contract matters
This standardization keeps the architecture readable, implementation-ready, and consistent across the specialist agents while preserving the Controller-only coordination role.
