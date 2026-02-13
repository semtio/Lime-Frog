import io
import logging
import os
import platform
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_file

from logging_config import setup_logging, cleanup_old_job_logs, get_job_log_path
from tabs.seo_checker.config import (
    CHECK_LABELS,
    DEFAULT_CHECK_OPTIONS,
    DEFAULT_RUNTIME_OPTIONS,
    CheckOptions,
    RuntimeOptions,
)
from tabs.seo_checker.exporters import (
    rows_to_csv_bytes,
    rows_to_headings_xlsx_bytes,
    rows_to_xlsx_bytes,
)
from tabs.seo_checker.jobs import JobManager

try:
    import psutil
except ImportError:  # pragma: no cover - optional
    psutil = None


job_manager = JobManager()


def create_app() -> Flask:
    # Настройка логирования
    logger = setup_logging()
    logger.info("Application starting...")

    # Очистка старых job-логов при старте
    cleanup_old_job_logs()

    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            defaults=DEFAULT_RUNTIME_OPTIONS.__dict__,
            checks=DEFAULT_CHECK_OPTIONS.to_dict(),
            labels=CHECK_LABELS,
        )

    @app.post("/api/job")
    def create_job():
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        raw_urls = payload.get("urls", "")
        url_list = [line.strip() for line in str(raw_urls).splitlines() if line.strip()]
        if not url_list:
            return jsonify({"error": "Список URL пуст"}), 400

        options_data = payload.get("options", {}) or {}
        runtime_data = payload.get("runtime", {}) or {}

        merged_opts = DEFAULT_CHECK_OPTIONS.to_dict()
        for key, value in options_data.items():
            if key in merged_opts:
                merged_opts[key] = bool(value)
        check_options = CheckOptions(**merged_opts)

        merged_runtime = DEFAULT_RUNTIME_OPTIONS.__dict__.copy()
        for key, value in runtime_data.items():
            try:
                merged_runtime[key] = int(value)
            except (TypeError, ValueError):
                continue
        runtime = RuntimeOptions(**merged_runtime)
        runtime.concurrency = max(1, min(runtime.concurrency, 10))
        runtime.timeout_seconds = max(3, min(runtime.timeout_seconds, 120))
        runtime.retries = max(0, min(runtime.retries, 5))

        job = job_manager.create_job(url_list, check_options, runtime)
        return jsonify({"job_id": job.id})

    @app.get("/api/job/<job_id>")
    def job_status(job_id: str):
        job = job_manager.get(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        snapshot = job_manager.status_snapshot(job)
        return jsonify(snapshot)

    @app.post("/api/job/<job_id>/stop")
    def stop_job(job_id: str):
        ok = job_manager.stop(job_id)
        return jsonify({"stopped": ok}), (200 if ok else 404)

    @app.get("/api/job/<job_id>/log")
    def download_job_log(job_id: str):
        """Скачивание лога конкретного job."""
        # Проверяем что job существует
        job = job_manager.get(job_id)
        if not job:
            return jsonify({"error": "job not found"}), 404

        # Получаем путь к лог-файлу
        log_path = get_job_log_path(job_id)

        # Проверяем что файл существует
        if not log_path.exists():
            return jsonify({"error": "log file not found (job may not have started yet)"}), 404

        # Отдаём файл как текст
        try:
            return send_file(
                log_path,
                as_attachment=True,
                download_name=f"seo_{job_id}.log",
                mimetype="text/plain; charset=utf-8"
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/job/<job_id>/download")
    def download_csv(job_id: str):
        results = job_manager.results(job_id)
        if results is None:
            return jsonify({"error": "not found"}), 404

        # Получить кастомное имя файла из query параметров
        custom_filename = request.args.get("filename", "").strip()
        if custom_filename:
            # Очистить имя файла от небезопасных символов
            safe_filename = "".join(
                c for c in custom_filename if c.isalnum() or c in ("-", "_", " ")
            )
            filename = (
                f"{safe_filename}.csv" if safe_filename else f"seo-check-{job_id}.csv"
            )
        else:
            filename = f"seo-check-{job_id}.csv"

        data = rows_to_csv_bytes(results)
        return send_file(
            io.BytesIO(data),
            as_attachment=True,
            download_name=filename,
            mimetype="text/csv; charset=utf-8",
        )

    @app.get("/api/job/<job_id>/download-xlsx")
    def download_xlsx(job_id: str):
        results = job_manager.results(job_id)
        if results is None:
            return jsonify({"error": "not found"}), 404

        # Получить кастомное имя файла из query параметров
        custom_filename = request.args.get("filename", "").strip()
        if custom_filename:
            # Очистить имя файла от небезопасных символов
            safe_filename = "".join(
                c for c in custom_filename if c.isalnum() or c in ("-", "_", " ")
            )
            filename = (
                f"{safe_filename}.xlsx" if safe_filename else f"seo-check-{job_id}.xlsx"
            )
        else:
            filename = f"seo-check-{job_id}.xlsx"

        try:
            data = rows_to_xlsx_bytes(results)
            return send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except ImportError as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/job/<job_id>/download-headings-xlsx")
    def download_headings_xlsx(job_id: str):
        results = job_manager.results(job_id)
        if results is None:
            return jsonify({"error": "not found"}), 404

        custom_filename = request.args.get("filename", "").strip()
        if custom_filename:
            safe_filename = "".join(
                c for c in custom_filename if c.isalnum() or c in ("-", "_", " ")
            )
            filename = (
                f"{safe_filename}-headings.xlsx"
                if safe_filename
                else f"seo-headings-{job_id}.xlsx"
            )
        else:
            filename = f"seo-headings-{job_id}.xlsx"

        # Получить список выбранных заголовков из query параметров
        enabled_headings_str = request.args.get("headings", "").strip()
        enabled_headings = None
        if enabled_headings_str:
            enabled_headings = [
                h.strip().upper() for h in enabled_headings_str.split(",")
            ]

        try:
            data = rows_to_headings_xlsx_bytes(
                results, enabled_headings=enabled_headings
            )
            return send_file(
                io.BytesIO(data),
                as_attachment=True,
                download_name=filename,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except ImportError as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/resource")
    def resource_usage():
        if platform.system().lower() != "linux" or not psutil:
            return jsonify({"available": False})
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        return jsonify(
            {
                "available": True,
                "cpu": cpu,
                "memory_percent": mem.percent,
            }
        )

    @app.get("/api/stats")
    def get_stats():
        """Возвращает статистику: количество активных пользователей и очередь."""
        stats = job_manager.get_stats()
        return jsonify(stats)

    @app.post("/api/heartbeat")
    def heartbeat():
        """Регистрирует heartbeat от активной вкладки."""
        payload = request.get_json(force=True, silent=True) or {}
        session_id = payload.get("session_id")
        if session_id:
            job_manager.heartbeat(session_id)
            return jsonify({"ok": True})
        return jsonify({"error": "session_id required"}), 400

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
