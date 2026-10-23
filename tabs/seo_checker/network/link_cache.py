"""One run's completed and in-flight link checks; no cross-job state."""
import asyncio
from typing import Awaitable, Callable, Optional


class LinkCheckCache:
    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    async def get(self, url: str, check: Callable[[], Awaitable[Optional[str]]]) -> Optional[str]:
        # All callers belong to the job's event loop. Register before awaiting
        # so concurrent pages also share the first request, not just its result.
        if url not in self._tasks:
            self._tasks[url] = asyncio.create_task(check())
        return await asyncio.shield(self._tasks[url])

    async def close(self):
        pending = [task for task in self._tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
