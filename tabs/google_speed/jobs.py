import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests

from job_gate import ActiveUserGate

from .exporters import rows_to_pagespeed_xlsx_bytes


PAGE_SPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
VALID_STRATEGIES = ["mobile", "desktop"]
VALID_CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]
CATEGORY_API_NAMES = {
    "performance": "PERFORMANCE",
    "accessibility": "ACCESSIBILITY",
    "best-practices": "BEST_PRACTICES",
    "seo": "SEO",
}
CATEGORY_RESULT_NAMES = {
    "performance": "performance",
    "accessibility": "accessibility",
    "best-practices": "best-practices",
    "seo": "seo",
}


@dataclass
class GoogleSpeedRuntime:
    concurrency: int
    request_timeout_seconds: int
    max_attempts_per_url: int
    retry_delay_seconds: float


class GoogleSpeedJob:
    def __init__(
        self,
        owner_session: str,
        urls: List[str],
        api_key: str,
        strategies: List[str],
        categories: List[str],
        runtime: GoogleSpeedRuntime,
        on_complete_callback=None,
    ) -> None:
        self.id = uuid.uuid4().hex
        self.owner_session = owner_session
        self.urls = urls
        self.api_key = api_key
        self.strategies = self._ordered_strategies(strategies)
        self.categories = self._ordered_categories(categories)
        self.runtime = runtime
        self.status: str = "queued"
        self.created_at = time.time()
        self.results: List[Tuple[int, Dict]] = []
        self.error: Optional[str] = None
        self.total = len(self.urls) * len(self.strategies)
        self.completed = 0
        self.queue_position: int = 0
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._on_complete = on_complete_callback

    @staticmethod
    def _ordered_strategies(strategies: List[str]) -> List[str]:
        ordered = []
        for strategy in VALID_STRATEGIES:
            if strategy in strategies:
                ordered.append(strategy)
        return ordered

    @staticmethod
    def _ordered_categories(categories: List[str]) -> List[str]:
        ordered = []
        for category in VALID_CATEGORIES:
            if category in categories:
                ordered.append(category)
        return ordered

    def _tasks(self) -> List[Tuple[int, str, str]]:
        tasks: List[Tuple[int, str, str]] = []
        idx = 0
        for strategy in self.strategies:
            for url in self.urls:
                tasks.append((idx, url, strategy))
                idx += 1
        return tasks

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def is_cancelled(self) -> bool:
        return self._cancel.is_set()

    def _run(self) -> None:
        self.status = "running"

        try:
            tasks = self._tasks()
            with ThreadPoolExecutor(max_workers=self.runtime.concurrency) as executor:
                futures = []
                for task_idx, url, strategy in tasks:
                    futures.append(
                        executor.submit(
                            self._process_single_check,
                            task_idx,
                            url,
                            strategy,
                        )
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

    def _process_single_check(self, task_idx: int, url: str, strategy: str) -> None:
        if self.is_cancelled():
            return

        result = self._check_url_with_retries(url=url, strategy=strategy)
        with self._lock:
            self.results.append((task_idx, result))
            self.completed += 1

    def _check_url_with_retries(self, url: str, strategy: str) -> Dict:
        attempts = 0
        final_result = None

        while attempts < self.runtime.max_attempts_per_url:
            if self.is_cancelled():
                return {
                    "url": url,
                    "strategy": strategy,
                    "scores": {cat: None for cat in self.categories},
                    "status": "stopped",
                    "error": "Остановлено пользователем",
                }

            attempts += 1
            final_result = self._check_url(url=url, strategy=strategy)

            if final_result.get("status") == "success":
                break

            if attempts < self.runtime.max_attempts_per_url:
                time.sleep(self.runtime.retry_delay_seconds)

        if final_result and final_result.get("status") != "success":
            final_result["error"] = (
                f"{final_result.get('error', 'Unknown')} (FAILED after {attempts} attempts)"
            )

        return final_result

    def _check_url(self, url: str, strategy: str) -> Dict:
        param_list = [("url", url), ("key", self.api_key), ("strategy", strategy)]
        for category in self.categories:
            param_list.append(("category", CATEGORY_API_NAMES.get(category, category)))

        try:
            response = requests.get(
                PAGE_SPEED_ENDPOINT,
                params=param_list,
                timeout=self.runtime.request_timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()

            categories_data = data.get("lighthouseResult", {}).get("categories", {})
            scores = {}
            missing_categories = []

            for category in self.categories:
                api_name = CATEGORY_RESULT_NAMES.get(category, category)
                score = categories_data.get(api_name, {}).get("score")
                if score is not None:
                    scores[category] = round(score * 100)
                else:
                    scores[category] = None
                    missing_categories.append(category)

            result = {
                "url": url,
                "strategy": strategy,
                "scores": scores,
                "status": "success" if not missing_categories else "warning",
                "performance_score": scores.get("performance"),
            }

            if missing_categories:
                result["error"] = f"Категории не найдены: {', '.join(missing_categories)}"

            return result

        except requests.exceptions.HTTPError:
            error_msg = f"HTTP ошибка {response.status_code}"
            try:
                error_details = response.json()
                if "error" in error_details:
                    error_msg += f": {error_details['error'].get('message', '')}"
            except Exception:
                pass

            return {
                "url": url,
                "strategy": strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": error_msg,
            }

        except requests.exceptions.Timeout:
            return {
                "url": url,
                "strategy": strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": "Таймаут запроса",
            }

        except requests.exceptions.RequestException as exc:
            return {
                "url": url,
                "strategy": strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": str(exc),
            }

        except Exception as exc:
            return {
                "url": url,
                "strategy": strategy,
                "performance_score": None,
                "scores": {cat: None for cat in self.categories},
                "status": "error",
                "error": f"Неожиданная ошибка: {str(exc)}",
            }


class GoogleSpeedJobManager:
    def __init__(self, gate: ActiveUserGate, max_parallel_owner: int = 6) -> None:
        self._jobs: Dict[str, GoogleSpeedJob] = {}
        self._lock = threading.Lock()
        self._queue: List[str] = []
        self._gate = gate
        self._max_parallel_owner = max_parallel_owner

    @staticmethod
    def normalize_urls(raw_urls: List[str]) -> List[str]:
        normalized = []
        for raw_url in raw_urls:
            value = str(raw_url).strip()
            if not value:
                continue
            if not value.startswith(("http://", "https://")):
                value = "https://" + value
            normalized.append(value)
        return normalized

    def create_job(
        self,
        owner_session: str,
        urls: List[str],
        api_key: str,
        strategies: List[str],
        categories: List[str],
        runtime: GoogleSpeedRuntime,
    ) -> GoogleSpeedJob:
        job = GoogleSpeedJob(
            owner_session=owner_session,
            urls=urls,
            api_key=api_key,
            strategies=strategies,
            categories=categories,
            runtime=runtime,
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

    def get(self, job_id: str) -> Optional[GoogleSpeedJob]:
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

    def status_snapshot(self, job: GoogleSpeedJob) -> Dict:
        return {
            "id": job.id,
            "status": job.status,
            "queue_position": job.queue_position,
            "total": job.total,
            "completed": job.completed,
            "error": job.error,
            "has_results": bool(job.results),
        }

    def results(self, job_id: str) -> Optional[List[Dict]]:
        job = self.get(job_id)
        if not job:
            return None
        return [row for _, row in sorted(job.results, key=lambda item: item[0])]

    def results_xlsx_bytes(self, job_id: str) -> Optional[bytes]:
        job = self.get(job_id)
        if not job:
            return None
        rows = self.results(job_id)
        if rows is None:
            return None
        return rows_to_pagespeed_xlsx_bytes(rows, job.strategies, job.categories)

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            running = sum(1 for job in self._jobs.values() if job.status == "running")
            queued = len(self._queue)
            return {"running": running, "queued": queued}
