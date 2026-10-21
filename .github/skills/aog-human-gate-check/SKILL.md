---
name: aog-human-gate-check
description: Verify that code, specs, and tests keep the advisory-only boundary and mandatory human approval, and that degraded evidence stays visible. Use before /opsx-verify or /opsx-archive, and when adding any tool, action, or fallback.
---

Source: ARD-PRN-001/002/006, ARD-GOV-001..008, ARD-RES-001..007, ARD-SEC-001..003/008, ARD-TST-005 in [architecture-requirements.md](../../../docs/architecture-requirements.md).

## Checks
1. **No execution**: no agent or tool performs an operational action (rebooking, ordering, transfers, dispatch). Tools are read-only or allowlisted (ARD-SEC-002/003).
2. **Approval record**: human actions are approve, reject, escalate, request-more-info; approval needs both Ops lead and Maintenance/airworthiness authority where applicable; the record includes case ID, action, selected option, reviewer, timestamp, rationale, recommendation version (ARD-GOV-006/007).
3. **Thresholds**: >=0.70 preferred but still approved by a human; 0.50–0.69 provisional; <0.50 escalate; conflicting evidence defers approval (ARD-GOV-001..004).
4. **No bypass**: no flag, test mode, degraded mode, or high confidence skips the gate (ARD-GOV-008).
5. **Degradation**: missing input yields a missing-data list, not assumptions; outages, timeouts, and stale data produce structured failures, partial recommendations labelled as such, and lower confidence (ARD-GOV-005, ARD-RES-001..006).
6. **Safety claims**: output does not claim airworthiness certification or regulatory approval (ARD-SEC-008).
7. **Tests exist** for each of the above (ARD-TST-005/007).

## Output
Pass/fail per check with file and line references and the violated ID; list blockers first.
