# FDE US03 Capstone Project

## Project Overview
This repository contains the design and proposal for an Aircraft-On-Ground (AOG) Recovery Coordinator built as a multi-agent decision support system using Google ADK.

The project focuses on helping airline operations teams respond to aircraft ground events faster, more consistently, and with clearer human oversight.

## Purpose
When an aircraft is grounded, multiple teams must act together quickly:
- Maintenance determines whether the aircraft can be repaired
- Inventory checks whether the required part is available
- Operations evaluates disruption to flights and fleet plans
- The Controller coordinates the work and prepares a recommendation for human approval

The system is designed to support better decisions without replacing human accountability.

## What This Project Solves
The capstone addresses a common airline operations problem:
- aircraft are grounded unexpectedly
- decisions are spread across several teams
- information is partial or conflicting
- recovery choices must balance technical feasibility, part availability, and operational impact

Without a coordinated system, teams can work in silos, causing longer downtime and slower recovery decisions.

## Core Business Idea
The system recommends the most likely recovery path using specialized agents, each focused on a different domain:
- Maintenance Agent: repairability and technical feasibility
- Inventory Agent: part availability and sourcing readiness
- Operations Agent: flight disruption and fleet impact
- Controller Agent: orchestration, routing, and approval workflow
- Report Creation Agent: final recommendation, ranking, and explanation

The final recommendation is always reviewed by a human before operational action is taken.

## Ubiquitous Language
This section defines the shared terms used across the project so everyone understands the same concepts.

### Aircraft-On-Ground (AOG)
A situation where an aircraft is unable to fly because of a technical issue, defect, or operational restriction.

### Recovery Decision
The choice of how to return an aircraft to service or minimize disruption, such as repair, part transfer, aircraft swap, reroute, or delay.

### Maintenance
The technical work required to assess the aircraft defect, determine repair feasibility, and estimate downtime.

### Inventory
The supply-side view of whether the required part or replacement material is available, missing, or can be transferred from another location.

### Operations
The schedule and fleet view that evaluates customer impact, route disruption, swap opportunities, and service continuity.

### Controller
The coordinating agent that receives the AOG event, routes work to specialists, consolidates findings, and manages the final recommendation path.

### Recommendation
The ranked option proposed to the human approver, based on technical, material, and operational evidence.

### Human-in-the-Loop
A governance model where AI provides decision support, but a human remains responsible for final approval and operational action.

### Confidence
The degree of trust in a recommendation based on evidence quality, completeness, and risk.

### Escalation
A decision path where the system pauses or asks for human intervention because the evidence is incomplete, conflicting, or low-confidence.

## Expected Outcomes
This project aims to:
- reduce aircraft downtime
- improve the speed and quality of recovery decisions
- provide explainable recommendations
- support coordinated decision-making across functions
- keep accountability with human operators

## Repository Structure
- [propsal.md](propsal.md) — detailed architecture and proposal document
- [agent-proposals](agent-proposals) — specialist agent design proposals
- [proposal_10-20.md](proposal_10-20.md) — alternate proposal stream for comparison and synthesis

## Project Status
This repository is currently in the proposal and architecture design phase for an enterprise AOG decision-support system.

## Summary
This capstone project is not just an AI demo. It is a structured operational decision-support concept for airline recovery planning, designed to combine specialist reasoning, policy guardrails, and human oversight into a practical AOG workflow.
