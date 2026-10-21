from contextlib import AbstractContextManager

from aog_recovery.contracts.case import TraceContext
from aog_recovery.observability.context import CorrelationContext, correlation_scope


def bind_invocation_context(
    case_id: str,
    trace_context: TraceContext,
    request_id: str | None = None,
) -> AbstractContextManager[CorrelationContext]:
    return correlation_scope(case_id, trace_context, request_id)
