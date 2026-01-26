import asyncio
import threading
import time
import uuid
from typing import Dict, List, Optional, Tuple

import httpx

from . import checks
from .config import CheckOptions, RuntimeOptions


class Job:
    def __init__(
        self, urls: List[str], check_options: CheckOptions, runtime: RuntimeOptions
    ):
        self.id = uuid.uuid4().hex
        self.urls = urls
        self.check_options = check_options
        self.runtime = runtime
        self.status: str = "pending"
        self.created_at = time.time()
        self.results: List[tuple[int, Dict[str, str]]] = []
        self.error: Optional[str] = None
        self.total = len(urls)
        self.completed = 0
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self):
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def _run(self):
        self.status = "running"
        try:
            asyncio.run(self._run_async())
            if self.is_cancelled():
                self.status = "stopped"
            elif self.error:
                self.status = "error"
            else:
                self.status = "completed"
        except Exception as exc:  # pragma: no cover - defensive
            self.error = str(exc)
            self.status = "error"

    async def _run_async(self):
        limits = httpx.Limits(
            max_keepalive_connections=self.runtime.concurrency,
            max_connections=self.runtime.concurrency * 2,
        )
        timeout = httpx.Timeout(self.runtime.timeout_seconds)
        async with httpx.AsyncClient(
            headers={"User-Agent": checks.USER_AGENT}, limits=limits, timeout=timeout
        ) as client:
            sem = asyncio.Semaphore(self.runtime.concurrency)
            tasks = [
                asyncio.create_task(self._process_single(idx, url, client, sem))
                for idx, url in enumerate(self.urls)
            ]
            await asyncio.gather(*tasks)

    async def _process_single(
        self, idx: int, url: str, client: httpx.AsyncClient, sem: asyncio.Semaphore
    ):
        if self.is_cancelled():
            return
        async with sem:
            if self.is_cancelled():
                return
            try:
                row = await checks.run_all_checks(
                    url, client, self.check_options, self.runtime
                )
            except Exception as exc:  # pragma: no cover - defensive
                row = {col: "" for col in checks.CSV_COLUMNS}
                row["URL"] = url
                row["Код ответа"] = f"ошибка: {exc}"[:200]
            with self._lock:
                self.results.append((idx, row))
                self.completed += 1


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(
        self, urls: List[str], check_options: CheckOptions, runtime: RuntimeOptions
    ) -> Job:
        job = Job(urls, check_options, runtime)
        with self._lock:
            self._jobs[job.id] = job
        job.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def stop(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        job.cancel()
        return True

    def status_snapshot(self, job: Job) -> Dict:
        return {
            "id": job.id,
            "status": job.status,
            "total": job.total,
            "completed": job.completed,
            "error": job.error,
            "has_results": bool(job.results),
        }

    def results(self, job_id: str) -> Optional[List[Dict[str, str]]]:
        job = self.get(job_id)
        if not job:
            return None
        return [row for _, row in sorted(job.results, key=lambda item: item[0])]
