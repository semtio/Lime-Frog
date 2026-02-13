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
        self,
        urls: List[str],
        check_options: CheckOptions,
        runtime: RuntimeOptions,
        on_complete_callback=None,
    ):
        self.id = uuid.uuid4().hex
        self.urls = urls
        self.check_options = check_options
        self.runtime = runtime
        self.status: str = "queued"  # Изменено с "pending" на "queued"
        self.created_at = time.time()
        self.results: List[tuple[int, Dict[str, str]]] = []
        self.error: Optional[str] = None
        self.total = len(urls)
        self.completed = 0
        self.queue_position: int = 0  # Позиция в очереди
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_complete = on_complete_callback

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
        finally:
            # Вызвать callback после завершения
            if self._on_complete:
                self._on_complete(self.id)

    async def _run_async(self):
        limits = httpx.Limits(
            max_keepalive_connections=self.runtime.concurrency,
            max_connections=self.runtime.concurrency * 2,
        )
        timeout = httpx.Timeout(self.runtime.timeout_seconds)
        async with httpx.AsyncClient(
            headers=checks.BROWSER_HEADERS, limits=limits, timeout=timeout
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
    def __init__(self, max_concurrent_jobs: int = 1):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_concurrent = max_concurrent_jobs
        self._queue: List[str] = []  # Очередь job_id
        self._sessions: Dict[str, float] = {}  # session_id -> last_heartbeat_time
        self._session_timeout = 10  # Таймаут сессии в секундах

    def create_job(
        self, urls: List[str], check_options: CheckOptions, runtime: RuntimeOptions
    ) -> Job:
        job = Job(
            urls, check_options, runtime, on_complete_callback=self._on_job_complete
        )
        with self._lock:
            self._jobs[job.id] = job
            self._queue.append(job.id)
            self._update_queue_positions()
            self._process_queue()
        return job

    def _on_job_complete(self, job_id: str):
        """Обработчик завершения задачи - запускает следующую из очереди."""
        with self._lock:
            self._process_queue()

    def _update_queue_positions(self):
        """Обновляет позиции в очереди для всех задач."""
        for idx, job_id in enumerate(self._queue):
            job = self._jobs.get(job_id)
            if job and job.status == "queued":
                job.queue_position = idx + 1

    def _process_queue(self):
        """Запускает задачи из очереди, если есть свободные слоты."""
        running_count = sum(1 for job in self._jobs.values() if job.status == "running")

        while running_count < self._max_concurrent and self._queue:
            job_id = self._queue[0]
            job = self._jobs.get(job_id)

            if job and job.status == "queued":
                self._queue.pop(0)
                job.queue_position = 0
                job.start()
                running_count += 1
                self._update_queue_positions()
            else:
                # Удаляем завершенные/остановленные задачи из очереди
                self._queue.pop(0)
                self._update_queue_positions()

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def stop(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        job.cancel()

        # Удалить из очереди и обработать следующую
        with self._lock:
            if job_id in self._queue:
                self._queue.remove(job_id)
                self._update_queue_positions()
            self._process_queue()

        return True

    def status_snapshot(self, job: Job) -> Dict:
        return {
            "id": job.id,
            "status": job.status,
            "queue_position": job.queue_position,
            "total": job.total,
            "completed": job.completed,
            "error": job.error,
            "has_results": bool(job.results),
        }

    def get_stats(self) -> Dict:
        """Возвращает статистику: количество активных пользователей и очередь."""
        with self._lock:
            # Очистить устаревшие сессии
            self._cleanup_sessions()

            active_jobs = sum(
                1 for job in self._jobs.values() if job.status in ("running", "queued")
            )
            running_jobs = sum(
                1 for job in self._jobs.values() if job.status == "running"
            )
            queued_jobs = len(self._queue)

            # Количество активных пользователей = количество активных сессий
            active_users = len(self._sessions)

            return {
                "active_users": active_users,
                "running": running_jobs,
                "queued": queued_jobs,
                "max_concurrent": self._max_concurrent,
            }

    def heartbeat(self, session_id: str):
        """Регистрирует heartbeat от активной вкладки."""
        with self._lock:
            self._sessions[session_id] = time.time()

    def _cleanup_sessions(self):
        """Удаляет устаревшие сессии."""
        current_time = time.time()
        expired = [
            sid
            for sid, last_time in self._sessions.items()
            if current_time - last_time > self._session_timeout
        ]
        for sid in expired:
            del self._sessions[sid]

    def results(self, job_id: str) -> Optional[List[Dict[str, str]]]:
        job = self.get(job_id)
        if not job:
            return None
        return [row for _, row in sorted(job.results, key=lambda item: item[0])]
