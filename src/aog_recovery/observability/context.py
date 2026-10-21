from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass

from aog_recovery.contracts.case import TraceContext


@dataclass(frozen=True, slots=True)
class CorrelationContext:
    case_id: str
    trace_id: str
    correlation_id: str
    request_id: str | None


_correlation_context: ContextVar[CorrelationContext | None] = ContextVar(
    "aog_correlation_context", default=None
)


def current_correlation_context() -> CorrelationContext | None:
    return _correlation_context.get()


@contextmanager
def correlation_scope(
    case_id: str,
    trace_context: TraceContext,
    request_id: str | None = None,
) -> Iterator[CorrelationContext]:
    context = CorrelationContext(
        case_id=case_id,
        trace_id=trace_context.trace_id,
        correlation_id=trace_context.correlation_id,
        request_id=request_id,
    )
    token: Token[CorrelationContext | None] = _correlation_context.set(context)
    try:
        yield context
    finally:
        _correlation_context.reset(token)
