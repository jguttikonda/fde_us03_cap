# Operations Agent Proposal Draft

This document is a detailed draft for the Operations Agent and supplements the root system proposal in ../propsal.md.

## 0. Shared Contract Reference
This draft follows the canonical agent contract defined in [AGENT_CONTRACT_TEMPLATE.md](AGENT_CONTRACT_TEMPLATE.md). All specialist proposals use the same structure and section ordering to preserve consistency across the architecture.

## 1. Purpose
The Operations Agent evaluates the business and schedule impact of an AOG event and recommends the operational path that minimizes disruption while remaining feasible.

## 2. Role in the System
This agent focuses on the fleet and network implications of each recovery option. It looks beyond the aircraft itself to understand route disruption, schedule risk, and the cost of delay, rerouting, or substitution.

## 3. Primary Responsibilities
- Evaluate flight and route impact
- Assess aircraft substitution options
- Measure schedule and customer disruption
- Recommend the least-disruptive operational path
- Prioritize recovery actions based on business effect

## 4. LLM Role
The Operations LLM acts as the disruption and prioritization analyst. It reasons over flight schedule, fleet availability, crew planning, route dependencies, and operational constraints to determine the most practical recovery strategy.

## 5. LLM Prompt Template
```text
You are the Operations Agent for an aircraft AOG recovery workflow.

Your task is to assess the operational impact of the outage and recommend the least-disruptive recovery path that is still feasible.

Inputs you must assess:
- Flight schedules and route disruptions
- Fleet availability and replacement aircraft candidates
- Crew and station constraints
- Customer service priority and operational importance
- Recovery options from maintenance and inventory teams

Decision rules:
- Evaluate which flights or routes are affected.
- Assess whether swap, delay, or reroute is the least-bad option.
- Consider business priority, customer impact, and schedule risk.
- Recommend the path with the best operational balance between disruption and feasibility.
- State the assumptions and confidence behind the recommendation.

Return only a structured operational impact assessment with:
1. disrupted flights and routes
2. recovery option comparison
3. schedule impact estimate
4. risk and assumptions
5. final operational recommendation
```

## 6. Expected Output Standard Format
```json
{
  "agent_name": "Operations Agent",
  "operational_impact_level": "low|medium|high|critical",
  "summary": "Short summary of the schedule and fleet impact",
  "affected_routes": ["Route 1", "Route 2"],
  "recovery_options": [
    {
      "option": "repair|swap|reroute|delay",
      "estimated_impact": "Low / Medium / High",
      "rationale": "Why this option is plausible"
    }
  ],
  "risk_factors": [
    "Risk 1",
    "Risk 2"
  ],
  "assumptions": [
    "Assumption 1",
    "Assumption 2"
  ],
  "recommendation": {
    "decision": "repair|swap|reroute|delay|escalate",
    "confidence": 0.0,
    "reasoning": "Why this operational path is preferred",
    "next_steps": ["Step 1", "Step 2"]
  }
}
```

## 7. Deterministic Responsibilities
- Validate flight and schedule data
- Detect route conflicts and aircraft assignment issues
- Apply standard substitution rules and disruption thresholds
- Compute basic impact categories and priority logic
- Maintain structured outputs for route and fleet implications

## 8. Non-Deterministic Responsibilities
- Determine which disruption pattern is most damaging under uncertainty
- Assess whether a delay, reroute, or aircraft swap is the least-bad option
- Balance customer impact against recovery efficiency
- Prioritize among multiple operational options when the trade-off is ambiguous
- Interpret dynamic schedule pressure in business terms

## 9. LLM-Facing Inputs
These are the inputs the LLM should reason over to assess operational impact:
- Flight schedules and route dependencies
- Fleet availability and substitute aircraft candidates
- Customer or service-critical flight context
- Crew and operational constraints affecting feasibility
- Route disruption assumptions and schedule sensitivity

## 10. Tool / External System Inputs
These are the structured system inputs consumed by the agent:
- Flight operations schedule systems
- Fleet assignment and aircraft availability feeds
- Network disruption and route impact data
- Crew and station planning context
- Customer service priority or service recovery rules

## 11. LLM-Facing Outputs
These are the outputs the LLM should produce as reasoning and recommendation artifacts:
- Operational impact summary
- Recovery path comparison
- Schedule disruption estimate
- Fleet substitution recommendation
- Recommended operational action with rationale

## 12. Tool / External System Outputs
These are the downstream system artifacts generated after reasoning:
- Operational impact payload sent to the Controller
- Flight and fleet adjustment recommendation record
- Customer impact summary or service-priority alert
- Schedule change flag for downstream planning systems
- Final decision context for approval or escalation

## 13. Validation and Output Evaluation
The Operations Agent should confirm:
- whether the recommendation is consistent with fleet constraints
- whether the effect on service is properly framed
- whether the operational path is realistic under current planning conditions
- whether the decision is actionable for the human approver

## 14. Questions This Agent Seeks to Answer
- Which flights or routes are impacted by the outage?
- Is substitution or rerouting feasible?
- What is the cost of delay, reroute, or alternate recovery?
- Which recovery option minimizes disruption while staying realistic?
- What is the operational impact on schedule reliability and customer commitments?

## 15. Acceptance Criteria
The Operations Agent is successful when it:
- provides a credible operational impact analysis
- highlights schedule trade-offs clearly
- supports the Controller with an operational recommendation that makes sense under disruption
- helps choose the least expensive and least disruptive practical path

## 16. Draft Notes
This agent turns a technical recovery problem into a business recovery decision. It ensures the final recommendation is not only technically possible but also operationally sensible in real-world conditions.
