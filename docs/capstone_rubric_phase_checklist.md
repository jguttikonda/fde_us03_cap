# Capstone Rubric Phase Checklist

This document maps the project delivery flow to the FDE Capstone rubric and RAPID expectations so the team can track readiness from proposal through demonstration.

## Phase 1: Proposal Drafting Stage

Goal: Validate that the concept is coherent and ready to move into OpenSpec and implementation planning.

Checklist:
- Problem statement is clear
  - business problem is identified
  - affected stakeholders are known
  - need for the solution is explained
- Value proposition is clear
  - main pain addressed
  - expected gains in speed, quality, or risk reduction
- Scope is explicit
  - in-scope capabilities identified
  - out-of-scope items defined
  - assumptions and constraints documented
- Architecture is understandable
  - Controller (Recovery Coordinator, including recommendation and report), Maintenance, Materials & Logistics, and Operations roles are clear
  - human approval and escalation model is visible
- Proposal is coherent
  - why the change is needed
  - what is being proposed
  - expected impact is stated
- Agent responsibilities are distinct
  - no unclear role overlap
- Decision logic is explainable
  - recommendation logic and escalation logic are understandable
- Evidence trail is visible
  - proposal reflects reasoning and iteration
  - not created only at the end as a final artifact

Rubric tie-in:
- Category 2: Spec-driven design quality
- Category 5: AI-assisted development practice
- Category 6: Demonstration and communication

Exit gate:
- Proposal is strong enough to hand off to OpenSpec and implementation planning.

---

## Phase 2: OpenSpec Conversion Stage

Goal: Convert the proposal into implementation-ready engineering artifacts.

Checklist:
- OpenSpec proposal exists and is coherent
- Proposal includes:
  - problem
  - proposed change
  - expected impact
  - rationale
- Implementation checklist exists
  - tasks are explicit
  - scope is tracked
  - work is broken into executable units
- Design document exists where needed
  - non-trivial decisions are justified
  - architecture choices are documented
- Spec deltas are captured
  - what changed from original proposal
  - what was added, modified, or removed
- Pydantic models are defined
  - structured outputs are typed
  - validation rules are explicit
- Tool contracts are defined
  - tool purpose
  - valid inputs
  - expected outputs
  - error and fallback behavior
- Agent workflow is mapped to scenarios
  - happy path
  - edge case
  - partial data
  - low confidence
  - human escalation path

Rubric tie-in:
- Category 2: Spec-driven design quality
- Category 1: Agent functionality and correctness
- Category 3: Engineering quality

Exit gate:
- There is a clear bridge from proposal to spec to implementation plan.

---

## Phase 3: Implementation Stage

Goal: Build the actual agent and supporting code.

Checklist:
- Agent runs end to end on defined scenarios
- Tool calls are valid and intentional
- Tool docstrings are clear enough to support correct selection
- Agent output conforms to typed models
- Final decision includes rationale tied to evidence
- Structured output is consistent
  - approve / deny / escalate / go / no-go
  - not just free-form narrative
- Tool layer handles valid arguments
- Full execution trajectory is traceable
  - not only final answer
- Error handling is present
  - tool failures are handled
  - fallback path exists
- Partial-data scenarios are supported
  - missing data does not silently turn into a confident answer
  - low-confidence output is escalated or downgraded
- Secrets are not hardcoded
- Naming and structure are readable
- Guardrails exist
  - schema validation
  - refusal or escalation for out-of-policy requests
  - invalid inputs rejected

Rubric tie-in:
- Category 1: Agent functionality and correctness
- Category 3: Engineering quality

Exit gate:
- The implementation can execute real scenarios without crashing and with structured output.

---

## Phase 4: Testing Stage

Goal: Prove the agent behaves correctly under normal and edge conditions.

Checklist:
- Tool tests exist
- Decision logic tests exist
- Edge-case tests exist
  - partial data
  - missing fields
  - conflicting inputs
  - unavailable tools
  - low-confidence decisions
- Output validation tests exist
  - schema conformance
  - required fields present
  - invalid output rejected
- Fallback tests exist
  - tool unavailable
  - degraded recommendation path
  - partial recommendation supported
- Regression checks exist
  - known good scenarios still pass
- Evidence is captured
  - results summarized in project artifacts

Rubric tie-in:
- Category 1: Agent functionality and correctness
- Category 3: Engineering quality

Exit gate:
- The agent has evidence it works, not just a plausible design.

---

## Phase 5: Deployment / Readiness Stage

Goal: Confirm the work is ready to be approved for progression.

Checklist:
- Environment and dependency setup is defined
- Deployment approach is documented
- Security considerations are addressed
- No secrets or credentials are committed to the repo
- Backout plan exists
- Requirements are documented
- Code review is complete
- Test result summary is captured
- Outstanding issues are listed
- Decision rationale is evidence-backed
- RAPID Go/No-Go checklist is completed
- RAPID peer-review artifact is completed
- Summary recommendation is explicit
  - approved
  - approved with conditions
  - not approved
- Team can articulate where the agent output and team checklist align or diverge

Rubric tie-in:
- Category 4: RAPID controls execution
- Category 3: Engineering quality
- Category 2: Spec-driven design quality

Exit gate:
- The project is ready for sign-off, not just coding sign-off.

---

## Phase 6: Demonstration / Communication Stage

Goal: Show the project to sponsors in stakeholder-appropriate terms.

Checklist:
- Demo stays within the time limit
- Team explains not just what was built, but why it was designed that way
- Design choices are justified
- Team explains what they would do differently with more time
- Q&A is handled live
- Presentation is framed for sponsors, not peer engineers
- Demo highlights business value and solution outcomes
- Risks, caveats, and the human approval model are clear
- Final recommendation is understandable to a non-technical audience

Rubric tie-in:
- Category 6: Demonstration and communication

Exit gate:
- Sponsor-facing delivery is credible, concise, and aligned to project outcomes.

---

## Summary Readiness Gate

Use the following as the overall gate logic:

1. Proposal gate
   - Is the idea coherent and scoped?
2. OpenSpec gate
   - Can the engineering work be translated into actionable tasks?
3. Implementation gate
   - Does the system function?
4. Testing gate
   - Is the behavior proven?
5. RAPID/deployment gate
   - Is the work ready to be approved and backed out if needed?
6. Demo gate
   - Can the team clearly explain and defend the outcome?

## Current Project Status
The repository has implemented the advisory four-agent workflow with deterministic local/mock adapters and human approval boundaries. The Controller demo is available as an offline CLI and a local ADK Web root over four named synthetic scenarios; automated tests, coverage, static checks, strict OpenSpec validation, and project-owned Gitleaks scans are recorded. Qualified peer review, InfoSec/Reference Architecture assessment, team Go/No-Go, sponsor rehearsal/presentation, and operational approvals remain human responsibilities; no production or live-enterprise readiness is claimed.

## Documentation Reference
- [proposal.md](proposal.md)
- [agent-proposals](agent-proposals)
- [README.md](README.md)
- [FDE_Capstone_Rubric_v5.0.docx](FDE_Capstone_Rubric_v5.0.docx)
- [RAPID Framework v7.0 Published September 2025.pdf](RAPID%20Framework%20v7.0%20Published%20September%202025.pdf)
