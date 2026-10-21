# Shared Foundation Contracts

## AOG Case Intake

`AogCase` requires a case and aircraft identifier, event type, defect summary,
location, timezone-aware event and creation timestamps, supported schema
version, and trace context. Missing, malformed, unsupported, or extra intake
values are rejected; the contract does not synthesize operational defaults.

## Provenance and Degraded Evidence

Evidence carries its source, retrieval time, validity state, content, and claim
reference. Partial, stale, and conflicting states remain explicit. Assumptions,
unknowns, warnings, and conflicts have distinct typed records; unknown claims
are not promoted to confirmed evidence.

## Agent Results and Recovery Options

Agent results use a versioned common envelope with a bounded confidence value
and a generic role-payload boundary. The contract validates shape only; it does
not implement specialist reasoning or treat a result as an approval. Structured
errors preserve failure category and case impact. Recovery options contain
evidence and assumptions but no score or approval state.

## Tool Results, Human Decisions, and Audit Events

Tool requests declare read-only access and carry request, case, and trace
correlation. Results carry source and status; failures require a structured
error and cannot carry success data. Human decision records are separate from
agent outputs and bind the reviewer role and rationale to a recommendation
version. Audit events retain case/trace metadata and concise structured details.

## Confidence Assessment

Confidence at or above 0.70 is preferred, 0.50 through below 0.70 is
provisional, and below 0.50 requires escalation. Any supplied material conflict
forces escalation regardless of confidence. Explicit unknown claim references
are preserved, and every disposition still requires human approval.

The human gate accepts only decision records that match the active case and
recommendation version. Repair or part approval requires Ops lead and
Maintenance/airworthiness approvals for the same selected action and option.
Agent results and confidence are not gate inputs.

Audit serialization redacts nested credential, contact, and private-reasoning
fields before JSON encoding. Audit records are delivered through an append-only
sink interface and retain concise rationale and evidence references rather
than private chain-of-thought.

The local adapter can deterministically represent unavailable, timeout,
malformed, stale, partial, and conflicting responses. Failures carry structured
errors with no data; degraded results retain partial data and warnings. The
foundation performs no automatic retries or success-shaped fallback.

## Future Live Adapter Boundary

The current adapters use local synthetic fixtures and require no enterprise
connectivity. A live adapter must be proposed and approved separately before
implementation; that change must define credential handling, least-privilege
permissions, transport and timeout behavior, and security verification. It must
preserve the typed read-only protocol and must not add operational write
capabilities.

## Runtime Settings

Settings are loaded from `AOG_`-prefixed environment variables. Adapter mode is
local-only in this foundation; timeout values are bounded and confidence
thresholds are validated for ordering. An optional provider secret is held as a
secret type and excluded from representations and serialized settings.