# Spec Delta

## Purpose

Lets an end user describe an aircraft-on-ground case conversationally and receive the Controller's validated, evidence-backed recovery brief in a readable chat response.

## ADDED Requirements

### Requirement: Accept conversational AOG intake

The chat MUST accept a user's AOG description, extract only supported case fields, and validate them before the case is routed.

#### Scenario: User submits a complete AOG description
- **WHEN** the user supplies all required case details in chat
- **THEN** the system confirms the case context and submits the validated case to the Controller workflow (ARD-CTL-001, ARD-CTL-004)

#### Scenario: User omits required details
- **WHEN** the user prompt lacks required case information
- **THEN** the chat asks concise field-specific follow-up questions and does not imply that specialist analysis or a recommendation is complete (ARD-CTL-002, ARD-GOV-005)

### Requirement: Present Controller results in plain language

The chat MUST render the Controller's structured decision brief as a clear response that preserves option facts, evidence references, uncertainty, confidence, exclusions, and required human action.

#### Scenario: Controller returns a decision brief
- **WHEN** the Controller returns a complete or provisional brief
- **THEN** the chat summarizes the recommendation and alternatives in readable language without changing their values, ranking, status, or caveats (ARD-CTL-013, ARD-CTL-014, ARD-CTL-016, ARD-PRN-005)

#### Scenario: Controller escalates or cannot recommend
- **WHEN** evidence conflicts, confidence is low, or required analysis is missing
- **THEN** the chat explains what is unknown or conflicting and what human review or information is needed (ARD-CTL-007, ARD-CTL-008, ARD-GOV-003, ARD-GOV-004)

### Requirement: Isolate chat case context

The chat MUST associate conversation state and displayed results with one explicit AOG case and MUST NOT expose or mix another case's context.

#### Scenario: Two cases are handled independently
- **WHEN** two distinct AOG cases are discussed in separate case contexts
- **THEN** messages, evidence, specialist results, and responses remain associated with their own case identifiers (ARD-CTL-005, ARD-RES-007)

### Requirement: Treat user and retrieved content as untrusted

The chat MUST NOT allow user text or retrieved data to change system policy, grant tool access, bypass validation, or weaken approval requirements.

#### Scenario: User requests an out-of-policy action
- **WHEN** a user asks the system to perform or automatically approve an operational action
- **THEN** the chat states that it provides advisory support only and routes the user to the required human approver without performing the action (ARD-PRN-001, ARD-PRN-002, ARD-SEC-005, ARD-GOV-008)

#### Scenario: Input contains instructions to bypass safeguards
- **WHEN** user-provided or retrieved text instructs the system to ignore policy, fabricate evidence, or claim approval
- **THEN** the system treats that text as untrusted data, follows the fixed policy, and reports only validated findings (ARD-SEC-004, ARD-SEC-005, ARD-SEC-008)

### Requirement: Show failures and degradation in chat

The chat MUST distinguish completed analysis from partial, failed, or unavailable analysis and MUST NOT present a success-shaped response when required processing fails.

#### Scenario: Specialist or data source fails
- **WHEN** a specialist or required source fails or times out
- **THEN** the response names the affected analysis, shows available results as partial where valid, and explains the escalation or next step (ARD-RES-002, ARD-RES-003, ARD-RES-004, ARD-RES-006)

### Requirement: Keep chat advisory and approval-required

Every recovery brief shown in chat MUST state that it is advisory and MUST require human approval before operational action.

#### Scenario: Any confidence or test mode is returned
- **WHEN** a brief is displayed in normal, high-confidence, provisional, degraded, or test mode
- **THEN** the response keeps human approval visible and never treats a chat reply as an approval record (ARD-PRN-001, ARD-PRN-002, ARD-GOV-001, ARD-GOV-002, ARD-GOV-008, ARD-TST-005)