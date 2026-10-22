"""Bounded asynchronous Controller adapter for synchronous Operations assessment."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from typing import Protocol

from aog_recovery.config import AogSettings
from aog_recovery.operations.models import OperationsOutcome, OperationsRequest


class SynchronousOperationsAgent(Protocol):
    def assess(self, request: OperationsRequest) -> OperationsOutcome: ...


class OperationsCapacityError(RuntimeError):
    """Raised when all bounded Operations workers still have active work."""


class OperationsDeadlineExceeded(TimeoutError):
    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(f"Operations assessment exceeded {timeout_seconds} seconds")
        self.timeout_seconds = timeout_seconds


class BoundedAsyncOperationsAdapter:
    def __init__(
        self,
        agent: SynchronousOperationsAgent,
        settings: AogSettings | None = None,
    ) -> None:
        self._settings = settings or AogSettings()
        self._agent = agent
        self._executor = ThreadPoolExecutor(
            max_workers=self._settings.operations_max_workers,
            thread_name_prefix="aog-operations",
        )
        self._worker_slots = BoundedSemaphore(self._settings.operations_max_workers)

    async def assess(self, request: OperationsRequest) -> OperationsOutcome:
        if not self._worker_slots.acquire(blocking=False):
            raise OperationsCapacityError("all bounded Operations workers are occupied")
        try:
            worker = self._executor.submit(self._agent.assess, request)
        except BaseException:
            self._worker_slots.release()
            raise

        worker.add_done_callback(lambda _: self._worker_slots.release())
        try:
            return await asyncio.wait_for(
                asyncio.wrap_future(worker),
                timeout=self._settings.operations_timeout_seconds,
            )
        except TimeoutError as error:
            worker.cancel()
            raise OperationsDeadlineExceeded(self._settings.operations_timeout_seconds) from error
