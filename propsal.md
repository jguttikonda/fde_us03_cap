
# Aircraft-On-Ground (AOG) Recovery Coordinator
## FDEUS03 Capstone Project
### Agent-to-Agent (A2A) Recovery Decision Support System using Google ADK

> Enterprise Capstone Proposal for Air Operations Workbench

---

# 1. Executive Summary

The Aircraft-On-Ground (AOG) Recovery Coordinator is an Agent-to-Agent (A2A) solution built using Google ADK. The platform orchestrates specialized agents across Maintenance, Inventory, Operations, and Recommendation management to recommend the optimal aircraft recovery strategy.

The goal is to reduce AOG duration, improve decision quality, and provide explainable recommendations while keeping the human operator in the loop for final approval.

Key goals:
- Reduce aircraft downtime
- Improve recovery decision quality
- Enable explainable recommendations
- Demonstrate enterprise-grade multi-agent orchestration
- Maintain human approval for operational actions

---

# 2. Business Problem

When an aircraft becomes AOG, multiple teams must coordinate quickly across technical and operational domains.

Typical questions include:
- Can the aircraft be repaired?
- Is the required part available?
- Can another aircraft be substituted?
- What is the operational impact of delaying or rerouting flights?

Without a coordinated system, teams often work in silos, creating delays, duplicate analysis, and slower recovery decisions.

---

# 3. Value Proposition

Benefits:
- Faster recovery decisions
- Reduced aircraft downtime
- Improved fleet utilization
- Better inventory visibility
- Clearer trade-off analysis across recovery options
- Explainable decision support for human operators

---

# 4. Why A2A vs Deterministic Solutions

Deterministic systems typically follow rules such as:

```text
IF part available THEN repair
```

Agentic systems evaluate multiple operational paths, including:

```text
Repair Now
Transfer Part
Swap Aircraft
Delay Flight
Use Alternate Recovery Plan
```

The system recommends the best option based on evidence rather than a single hard-coded rule.

---

# 5. Solution Overview

The Recovery Coordinator orchestrates a focused decision flow led by the Controller Agent. The controller receives the AOG event, delegates to the specialist agents, and then routes the recommendation to the human decision-maker for approval.

```mermaid
flowchart TB
    Controller[Controller Agent] --> Maintenance[Maintenance Agent]
    Controller --> Operations[Operations Agent]
    Controller --> Report[Report Creation Agent]
    Maintenance --> Inventory[Inventory Agent]
    Inventory --> Maintenance
    Operations --> Controller
    Report --> Human[Human]
    Human --> Final[Final Report]
```

This mirrors the image pattern: the Controller is at the top, the Maintenance and Operations branches are subordinate, Inventory is tied to the maintenance workflow, and the final recommendation is delivered to the Human for approval.

---

# 6. Agent Architecture

## Controller Agent
The Controller Agent is the main orchestrator. It receives the AOG event, delegates analysis to specialist agents, consolidates findings, and drives the final recommendation to the human decision-maker.

Responsibilities:
- Orchestration
- Planning
- Recommendation generation
- Coordination across specialist agents

## Maintenance Agent
The Maintenance Agent assesses aircraft repairability and technical feasibility. It evaluates whether the aircraft can be recovered through repair and estimates practical maintenance constraints.

- Repair analysis
- Work package feasibility
- Maintenance turnaround estimation
- Technical recovery assessment

## Inventory Agent
The Inventory Agent supports maintenance-driven part validation. It checks whether the required material is available and whether alternate sourcing is feasible.

- Inventory analysis
- Part availability validation
- Alternate part sourcing evaluation
- Material readiness assessment

## Operations Agent
The Operations Agent evaluates the larger business impact of the AOG event, including schedule and substitution implications. It assesses how the recovery path affects operations and customer impact.

- Flight impact analysis
- Swap recommendation evaluation
- Schedule disruption analysis
- Operational prioritization

## Report Creation Agent
The Report Creation Agent consolidates the output from the other agents and prepares a final recommendation package for human review.

- Consolidates findings from other agents
- Produces the ranked recovery recommendation
- Highlights trade-offs, assumptions, and risks
- Prepares the final recommendation for human approval

---

# 7. High-Level Architecture Diagram

```mermaid
flowchart TB
    User[User / Trigger Event] --> Validation[Input Prompt Validation]
    Validation --> Controller[Controller Agent]
    Controller --> Context[Context Engineering + Retrieval]
    Context --> LLM[LLM Reasoning Layer]

    Controller --> Maintenance[Maintenance Agent]
    Controller --> Operations[Operations Agent]
    Controller --> Report[Report Creation Agent]

    Maintenance --> Inventory[Inventory Agent]
    Inventory --> Maintenance

    Maintenance --> MCPM[MCP / Tool Layer]
    Inventory --> MCPI[MCP / Tool Layer]
    Operations --> MCPO[MCP / Tool Layer]
    Report --> MCPR[MCP / Tool Layer]

    MCPM --> MAPI[Maintenance APIs / Systems]
    MCPI --> IAPI[Inventory APIs / Systems]
    MCPO --> OAPI[Flight Ops APIs / Systems]
    MCPR --> RAPI[Recommendation / Reporting Layer]

    LLM --> AgentOut[Structured Agent Output]
    AgentOut --> Eval[Output Evaluation + Guardrails]
    Eval --> Human[Human Approval]
    Human --> Final[Final Report]
```

This architecture extends the Solution Overview by showing how the system gathers and validates inputs before orchestration. The validated prompt enters the Controller Agent, which enriches it with contextual memory, retrieved data, and tool-access instructions. The LLM then reasons over the structured context and calls MCP-enabled tools to interact with maintenance, inventory, and operations systems.

Key design elements:
- Input prompt validation: checks for missing fields, invalid request structure, safety constraints, and incomplete AOG event data before agent execution.
- Context engineering: combines retrieved state, prior conversation history, domain instructions, and structured constraints to improve decision quality.
- MCP and API interaction: specialist agents call approved tools and external APIs through an MCP/tool layer to fetch live operational data without bypassing governance.
- LLM interaction: the model reasons over validated context and tool outputs to generate a ranked recovery recommendation.
- Output evaluation: the final response is evaluated for consistency, completeness, groundedness, and safety before it is presented to the human operator.
- Optimization techniques: prompt templating, retrieval grounding, role-specific instructions, structured output schemas, tool result summarization, and evaluation-based validation help improve reliability and reduce hallucination risk.

---

# 8. Sequence Diagram

```mermaid
sequenceDiagram
User->>Controller: Analyze AOG Event
Controller->>Maintenance: Assess aircraft repairability
Maintenance->>Inventory: Validate part availability
Inventory-->>Maintenance: Part feasibility result
Controller->>Operations: Evaluate schedule and operational impact
Controller->>Report: Consolidate findings and prepare recommendation
Report-->>User: Final recovery recommendation
User->>Controller: Human review and approval
```

---

# 9. Tool & API Mapping

| Agent | Functional Focus |
|---------|------------------|
| Maintenance | Work orders, maintenance records, repair feasibility |
| Inventory | Parts inventory, supplier availability, material readiness |
| Operations | Flight schedules, route impact, aircraft substitution |
| Report Creation | Recommendation synthesis and decision summary |

---

# 10. Security Guardrails

- Read-only access where possible
- Role-based access control
- Least privilege access
- Audit trail for recommendations
- Prompt injection awareness
- Tool whitelisting

---

# 11. Safety Controls

- Advisory only
- Human approval required
- Explainable outputs
- Operational safeguards
- Clear decision rationale

---

# 12. Human-in-the-Loop Governance

```text
AI Recommendation
    ↓
Human Review
    ↓
Human Approval
    ↓
Operational Action
```

This ensures the platform supports decision-making without bypassing accountability. The agent recommends; the human approves.

---

# 13. Expected Business Impact

The solution is intended to help air operations teams act faster when time-sensitive recovery decisions are needed. It brings together technical feasibility, material readiness, and operational disruption into a single coordinated decision flow.

Expected impact:
- Faster AOG response
- Better resource prioritization
- More consistent decision-making
- Greater visibility across teams
- Lower disruption from manual coordination delays

---

# 14. Final Positioning

This project is scoped to a focused Agent-to-Agent recovery decision support model aligned to the architecture shown in the image. It removes the Logistics and Risk Agent scope while preserving the core decision-making flow around the Controller, Maintenance, Inventory, Operations, and Report Creation agents.

The result is a clear, operationally relevant capstone solution that remains realistic, explainable, and suitable for a human-approved aircraft recovery process.
