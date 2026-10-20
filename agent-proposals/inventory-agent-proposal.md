# Inventory Agent Proposal Draft

This document is a detailed draft for the Inventory Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Inventory Agent determines whether the required parts and material are available to support the AOG recovery plan and whether alternate sourcing is realistic.

## 2. Role in the System
This agent supports the maintenance path by validating physical and logistical availability. It determines not just whether a part exists, but whether it can be obtained in time and with acceptable material risk.

## 3. Primary Responsibilities
- Part availability checking
- Alternate sourcing evaluation
- Supplier and station feasibility review
- Material readiness assessment
- Part substitution recommendation

## 4. LLM Role
The Inventory LLM acts as the materials readiness specialist. It interprets inventory data, stock locations, transfer rules, supplier constraints, and likely lead times to assess material readiness.

## 5. LLM Prompt Template
```text
You are the Inventory Agent for an aircraft AOG recovery workflow.

Your task is to assess whether the required part or material can be secured in time to support the aircraft recovery plan.

Inputs you must consider:
- Part number and current stock status
- Location-level availability and transfer constraints
- Alternate part options and compatibility rules
- Supplier or station readiness information
- Expected lead times and procurement constraints

Decision rules:
- Validate whether the part is available now or can be sourced quickly.
- Evaluate alternate part feasibility and risk if primary stock is unavailable.
- Clearly distinguish between confirmed availability and uncertain supply.
- Recommend the most realistic material path under time pressure.
- Include risk, assumptions, and time-to-delivery in the output.

Return only a structured material readiness assessment with:
1. availability status
2. sourcing path
3. lead time estimate
4. risk and assumptions
5. final recommendation
```

## 6. Expected Output Standard Format
```json
{
  "agent_name": "Inventory Agent",
  "availability_status": "available|limited|unavailable|uncertain",
  "summary": "Short summary of current material readiness",
  "sourcing_path": {
    "primary": "Primary source or stock location",
    "alternate": "Alternate or backup option",
    "transfer_required": true
  },
  "lead_time_hours": 0,
  "risk_factors": [
    "Risk 1",
    "Risk 2"
  ],
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "recommendation": {
    "decision": "source|transfer|substitute|escalate|delay",
    "confidence": 0.0,
    "reasoning": "Why this source path is most credible",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 7. Deterministic Responsibilities
- Validate stock counts and part-level metadata
- Check minimum availability thresholds
- Apply part substitution and sourcing rules
- Detect missing inventory or location inconsistencies
- Calculate expected lead times from structured data

## 8. Non-Deterministic Responsibilities
- Interpret stale or incomplete inventory data
- Judge whether alternate parts are operationally acceptable
- Assess supplier reliability and timing risk under uncertainty
- Recommend a path when inventory status is incomplete but time-sensitive
- Balance speed of availability against long-term recovery risk

## 9. LLM-Facing Inputs
These are the inputs the LLM should reason over to evaluate material readiness:
- Part number, specification, and usage context
- Stock quantity, location, and current availability
- Alternate part mappings and substitution suitability
- Supplier or station readiness notes and constraints
- Lead time and transfer assumptions for the shipment path

## 10. Tool / External System Inputs
These are the structured system inputs consumed by the agent:
- Inventory and warehouse service data
- Stock movement and transfer records
- Supplier and station availability feeds
- Alternate-part catalog and compatibility metadata
- Procurement or logistics workflow data

## 11. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts:
- Part availability status
- Alternate sourcing recommendation
- Lead-time estimate and supply risk summary
- Material readiness verdict
- Recommended sourcing path under urgency constraints

## 12. Tool / External System Outputs
These are the downstream system artifacts generated after reasoning:
- Material readiness status payload
- Procurement or transfer task recommendation
- Supplier escalation record if necessary
- Risk flag for missing or uncertain inventory data
- Decision summary passed to the Controller and Maintenance Agent

## 13. Validation and Output Evaluation
The Inventory Agent should confirm:
- whether the part is truly available or only theoretically available
- whether alternate sources are acceptable for the aircraft configuration
- whether the part can be delivered within the needed time window
- whether the recommendation is realistic under operational pressure

## 14. Questions This Agent Seeks to Answer
- Is the required part available right now?
- Can it be transferred or sourced elsewhere?
- How long will that take?
- Is an alternate replacement feasible without increasing risk?
- Which material path best supports the preferred recovery option?

## 15. Acceptance Criteria
The Inventory Agent is successful when it:
- distinguishes actual availability from theoretical availability
- provides a practical sourcing path for the required materials
- identifies risk or delay early enough for decision-making
- supports a realistic recovery plan instead of a purely ideal one

## 16. Draft Notes
This agent is essential when the aircraft is technically repairable but the part is the bottleneck. Its value is in materially grounded decision support for urgent recovery actions.
