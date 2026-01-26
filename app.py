import io
import os
import platform
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_file

from site_checker.config import (
    CHECK_LABELS,
    DEFAULT_CHECK_OPTIONS,
    DEFAULT_RUNTIME_OPTIONS,
    CheckOptions,
    RuntimeOptions,
)
from site_checker.exporters import rows_to_csv_bytes
from site_checker.jobs import JobManager

try:
    import psutil
except ImportError:  # pragma: no cover - optional
    psutil = None


job_manager = JobManager()


def create_app() -> Flask:
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

    @app.get("/api/job/<job_id>/download")
    def download_csv(job_id: str):
        results = job_manager.results(job_id)
        if results is None:
            return jsonify({"error": "not found"}), 404
        data = rows_to_csv_bytes(results)
        return send_file(
            io.BytesIO(data),
            as_attachment=True,
            download_name=f"seo-check-{job_id}.csv",
            mimetype="text/csv; charset=utf-8",
        )

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

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
