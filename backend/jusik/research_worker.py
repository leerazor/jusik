import asyncio
from collections.abc import Awaitable, Callable

from jusik.research_data import (
    DataCollectionError,
    DataInsufficientError,
    HistoricalDataProvider,
)
from jusik.research_engine import run_backtest, snapshot_hash
from jusik.research_store import ResearchStore

CompletedHandler = Callable[[str], Awaitable[None]]
TerminalHandler = Callable[[str, str], Awaitable[None]]


class ResearchWorker:
    def __init__(
        self,
        store: ResearchStore,
        provider: HistoricalDataProvider,
        on_completed: CompletedHandler | None = None,
        on_terminal: TerminalHandler | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10)
        self._task: asyncio.Task[None] | None = None
        self._on_completed = on_completed
        self._on_terminal = on_terminal
        self._enqueued: set[str] = set()

    def start(self) -> None:
        if self._task is not None:
            return
        self.store.recover_interrupted()
        self._task = asyncio.create_task(self._run())
        for run_id in self.store.queued_ids():
            self.enqueue(run_id)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def enqueue(self, run_id: str) -> None:
        if run_id in self._enqueued:
            return
        self._queue.put_nowait(run_id)
        self._enqueued.add(run_id)

    @property
    def queue_full(self) -> bool:
        return self._queue.full()

    async def _run(self) -> None:
        while True:
            run_id = await self._queue.get()
            try:
                await self._process(run_id)
            finally:
                self._enqueued.discard(run_id)
                self._queue.task_done()

    async def _process(self, run_id: str) -> None:
        try:
            run = self.store.get(run_id)
            if run.status != "queued":
                return
            snapshot = run.input_snapshot
            if snapshot is None:
                self.store.update_status(run_id, "collecting")
                snapshot = await self.provider.collect(run.request)
            self.store.save_snapshot(run_id, snapshot, snapshot_hash(snapshot))
            result = await asyncio.to_thread(run_backtest, run.request, snapshot)
            self.store.complete(run_id, result)
            if self._on_completed is not None:
                try:
                    await self._on_completed(run_id)
                except Exception:
                    # Deterministic research remains completed even when an optional
                    # post-processing integration fails.
                    pass
            await self._notify_terminal(run_id, "completed")
        except DataCollectionError as exc:
            self.store.fail(run_id, "failed", str(exc))
            await self._notify_terminal(run_id, "failed")
        except DataInsufficientError as exc:
            self.store.fail(run_id, "insufficient", str(exc))
            await self._notify_terminal(run_id, "insufficient")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.store.fail(
                run_id,
                "failed",
                "연구 실행에 실패했습니다. 모의 시세 서비스와 입력값을 확인하세요.",
            )
            await self._notify_terminal(run_id, "failed")

    async def _notify_terminal(self, run_id: str, outcome: str) -> None:
        if self._on_terminal is None:
            return
        try:
            await self._on_terminal(run_id, outcome)
        except Exception:
            # Journal failures cannot change immutable research outcomes.
            pass
