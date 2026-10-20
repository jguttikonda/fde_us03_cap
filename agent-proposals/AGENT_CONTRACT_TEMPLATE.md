# Agent Contract Template

This document is the canonical template for all specialist agent proposals in the AOG Recovery Coordinator design.

Use this as the standard contract for every agent draft.

## Shared Structure
Every proposal must include the following sections in order:

1. Purpose
2. Role in the System
3. Primary Responsibilities
4. LLM Role
5. LLM Prompt Template
6. Expected Output Standard Format
7. Deterministic Responsibilities
8. Non-Deterministic Responsibilities
9. LLM-Facing Inputs
10. Tool / External System Inputs
11. LLM-Facing Outputs
12. Tool / External System Outputs
13. Validation and Output Evaluation
14. Questions This Agent Seeks to Answer
15. Acceptance Criteria
16. Draft Notes

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

## 4. LLM Role
Define the reasoned behavior expected from the model and what it should not own.

## 5. LLM Prompt Template
```text
You are the [Agent Name] for an aircraft AOG recovery workflow.

Your task is to ...

Inputs you must assess:
- Input A
- Input B

Decision rules:
- Rule 1
- Rule 2
- Rule 3

Return only a structured output with:
1. result summary
2. required findings
3. recommendation
4. confidence
5. next action
```

## 6. Expected Output Standard Format
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

## 7. Deterministic Responsibilities
- Validate required structured inputs
- Apply known policy, thresholds, and route rules
- Detect missing data and enforce standard validation checks

## 8. Non-Deterministic Responsibilities
- Interpret ambiguity, partial evidence, and conflicting signals
- Recommend the best path under uncertain conditions
- Balance competing trade-offs and explain confidence

## 9. LLM-Facing Inputs
- Inputs the model should reason over as narrative or structured context

## 10. Tool / External System Inputs
- Structured system data from MCP tools, APIs, and operational feeds

## 11. LLM-Facing Outputs
- Outputs the model should produce for coordination and human review

## 12. Tool / External System Outputs
- Structured downstream artifacts, tasks, or records created after reasoning

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
