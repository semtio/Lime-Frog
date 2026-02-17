import threading
import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from job_gate import ActiveUserGate
from tabs.seo_checker.exporters import rows_to_xlsx_bytes
from .extract_anchor_text import process_line as process_anchor_line, DEFAULT_USER_AGENT
from .extract_alt_img import process_line as process_alt_line


@dataclass
class MagicLinksRuntime:
    concurrency: int
    timeout_seconds: int
    retries: int
    delay_seconds: float


class MagicLinksJob:
    def __init__(
        self,
        owner_session: str,
        pairs: List[Tuple[str, str]],
        mode: str,
        runtime: MagicLinksRuntime,
        on_complete_callback=None,
    ) -> None:
        self.id = uuid.uuid4().hex
        self.owner_session = owner_session
        self.pairs = pairs
        self.mode = mode
        self.runtime = runtime
        self.status: str = "queued"
        self.created_at = time.time()
        self.results: List[Tuple[int, Dict[str, str]]] = []
        self.error: Optional[str] = None
        self.total = len(pairs)
        self.completed = 0
        self.queue_position: int = 0
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_complete = on_complete_callback

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def _run(self) -> None:
        self.status = "running"
        session = requests.Session()
        session.headers.update({"User-Agent": DEFAULT_USER_AGENT})

        try:
            with ThreadPoolExecutor(max_workers=self.runtime.concurrency) as executor:
                futures = []
                for idx, pair in enumerate(self.pairs):
                    futures.append(
                        executor.submit(self._process_pair, idx, pair, session)
                    )
                for future in as_completed(futures):
                    if self.is_cancelled():
                        break
                    future.result()

            if self.is_cancelled():
                self.status = "stopped"
            elif self.error:
                self.status = "error"
            else:
                self.status = "completed"
        except Exception as exc:
            self.error = str(exc)
            self.status = "error"
        finally:
            if self._on_complete:
                self._on_complete(self.id)

    def _process_pair(
        self,
        idx: int,
        pair: Tuple[str, str],
        session: requests.Session,
    ) -> None:
        if self.is_cancelled():
            return

        if idx > 0 and self.runtime.delay_seconds > 0:
            time.sleep(self.runtime.delay_seconds)

        first_url, second_url = pair
        if not first_url or not second_url:
            row = {
                "first_url": first_url,
                "second_url": second_url,
                "status": "bad_input",
            }
            self._append_result(idx, row)
            return

        result = self._run_with_retries(session, first_url, second_url)
        if result is None:
            row = {
                "first_url": first_url,
                "second_url": second_url,
                "status": "stopped",
            }
            self._append_result(idx, row)
            return
        if self.mode == "alt":
            value = getattr(result, "image_alt", "")
            row = {
                "first_url": result.first_url,
                "second_url": result.second_url,
                "image_alt": value,
                "status": result.status,
            }
        else:
            value = getattr(result, "anchor_text", "")
            row = {
                "first_url": result.first_url,
                "second_url": result.second_url,
                "anchor_text": value,
                "status": result.status,
            }
        self._append_result(idx, row)

    def _run_with_retries(
        self,
        session: requests.Session,
        first_url: str,
        second_url: str,
    ):
        attempts = max(0, self.runtime.retries) + 1
        last_result = None
        for _ in range(attempts):
            if self.is_cancelled():
                break
            if self.mode == "alt":
                last_result = process_alt_line(
                    session, first_url, second_url, self.runtime.timeout_seconds
                )
            else:
                last_result = process_anchor_line(
                    session, first_url, second_url, self.runtime.timeout_seconds
                )

            if last_result.status == "ok" or last_result.status == "not_found":
                return last_result
        return last_result

    def _append_result(self, idx: int, row: Dict[str, str]) -> None:
        with self._lock:
            self.results.append((idx, row))
            self.completed += 1


class MagicLinksJobManager:
    def __init__(self, gate: ActiveUserGate, max_parallel_owner: int = 6) -> None:
        self._jobs: Dict[str, MagicLinksJob] = {}
        self._lock = threading.Lock()
        self._queue: List[str] = []
        self._gate = gate
        self._max_parallel_owner = max_parallel_owner

    def create_job(
        self,
        owner_session: str,
        pairs: List[Tuple[str, str]],
        mode: str,
        runtime: MagicLinksRuntime,
    ) -> MagicLinksJob:
        job = MagicLinksJob(
            owner_session,
            pairs,
            mode,
            runtime,
            on_complete_callback=self._on_job_complete,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._queue.append(job.id)
            self._update_queue_positions()
            self._process_queue()
        return job

    def _on_job_complete(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if job:
            self._gate.on_finish(job.owner_session)
        with self._lock:
            self._process_queue()

    def _update_queue_positions(self) -> None:
        for idx, job_id in enumerate(self._queue):
            job = self._jobs.get(job_id)
            if job and job.status == "queued":
                job.queue_position = idx + 1

    def _process_queue(self) -> None:
        active_owner = self._gate.active_owner()
        queued_job_ids = list(self._queue)

        if active_owner is None:
            for job_id in queued_job_ids:
                job = self._jobs.get(job_id)
                if job and job.status == "queued":
                    active_owner = job.owner_session
                    break

        if not active_owner:
            return

        for job_id in queued_job_ids:
            job = self._jobs.get(job_id)
            if not job or job.status != "queued":
                if job_id in self._queue:
                    self._queue.remove(job_id)
                continue

            if job.owner_session != active_owner:
                continue

            if not self._gate.can_start(active_owner, self._max_parallel_owner):
                break

            if job_id in self._queue:
                self._queue.remove(job_id)
            job.queue_position = 0
            self._gate.on_start(active_owner)
            job.start()

        self._update_queue_positions()

    def get(self, job_id: str) -> Optional[MagicLinksJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def stop(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        job.cancel()

        with self._lock:
            if job_id in self._queue:
                self._queue.remove(job_id)
                self._update_queue_positions()
            self._process_queue()

        return True

    def status_snapshot(self, job: MagicLinksJob) -> Dict:
        return {
            "id": job.id,
            "status": job.status,
            "queue_position": job.queue_position,
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

    def results_xlsx_bytes(self, job_id: str) -> Optional[bytes]:
        results = self.results(job_id)
        if results is None:
            return None
        return rows_to_xlsx_bytes(results)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            running = sum(1 for job in self._jobs.values() if job.status == "running")
            queued = len(self._queue)
            return {"running": running, "queued": queued}

    def queued_count_for_owner(self, owner_session: str) -> int:
        with self._lock:
            return sum(
                1
                for job_id in self._queue
                if (
                    self._jobs.get(job_id)
                    and self._jobs[job_id].owner_session == owner_session
                )
            )

    def total_count_for_owner(self, owner_session: str) -> int:
        with self._lock:
            return sum(
                1
                for job in self._jobs.values()
                if job.owner_session == owner_session
                and job.status in ("queued", "running")
            )
