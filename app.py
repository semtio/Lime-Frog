import io
import logging
import os
import platform
from functools import wraps
from typing import Any, Dict

import requests
from flask import Flask, jsonify, render_template, request, send_file

from auth import verify_credentials, create_session_token, verify_session_token
from logging_config import setup_logging, cleanup_old_job_logs, get_job_log_path
from tabs import get_default_module, get_module, get_registered_modules
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
from tabs.magic_links.jobs import MagicLinksJobManager, MagicLinksRuntime
from tabs.google_speed.jobs import (
    GoogleSpeedJobManager,
    GoogleSpeedRuntime,
    PAGE_SPEED_ENDPOINT,
    VALID_CATEGORIES,
    VALID_STRATEGIES,
)
from tabs.ssh_tools.routes import register_routes as register_ssh_routes
import tabs.seo_checker
import tabs.ssh_tools
import tabs.magic_links
import tabs.google_speed
from job_gate import ActiveUserGate

try:
    import psutil
except ImportError:  # pragma: no cover - optional
    psutil = None


gate = ActiveUserGate()
job_manager = JobManager(gate, max_concurrent_jobs=1, max_parallel_owner=6)
magic_links_manager = MagicLinksJobManager(gate, max_parallel_owner=6)
google_speed_manager = GoogleSpeedJobManager(gate, max_parallel_owner=6)


def require_auth(f):
    """Декоратор для защиты API endpoints - требует валидный токен."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Получаем токен из cookie
        token = request.cookies.get("auth_token")

        if not token or not verify_session_token(token):
            return jsonify({"error": "Unauthorized", "auth_required": True}), 401

        return f(*args, **kwargs)

    return decorated_function


def create_app() -> Flask:
    # Настройка логирования
    logger = setup_logging()
    logger.info("Application starting...")

    # Очистка старых job-логов при старте
    cleanup_old_job_logs()

    app = Flask(__name__)

    def render_tool_page(selected_tool: str):
        module = get_module(selected_tool) or get_default_module()
        tools = [tool.to_dict() for tool in get_registered_modules()]
        return render_template(
            "index.html",
            defaults=DEFAULT_RUNTIME_OPTIONS.__dict__,
            checks=DEFAULT_CHECK_OPTIONS.to_dict(),
            labels=CHECK_LABELS,
            tools=tools,
            selected_tool=module.name if module else "seo_checker",
            page_title=module.title if module else "SEO Checker",
            page_hint=module.description if module else "",
        )

    @app.route("/")
    def index():
        return render_tool_page("seo_checker")

    @app.route("/ssh-tools")
    def ssh_tools():
        return render_tool_page("ssh_tools")

    # ==================== Auth API ====================
    @app.post("/api/auth/login")
    def auth_login():
        """Аутентификация пользователя."""
        payload = request.get_json(force=True, silent=True) or {}
        username = payload.get("username", "").strip()
        password = payload.get("password", "").strip()

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        # Проверка учетных данных
        if verify_credentials(username, password):
            token = create_session_token()
            response = jsonify({"success": True, "token": token})
            # Устанавливаем cookie с токеном (30 дней)
            response.set_cookie(
                "auth_token",
                token,
                max_age=30 * 24 * 60 * 60,  # 30 дней
                httponly=True,
                samesite="Lax",
            )
            return response
        else:
            return jsonify({"error": "Invalid credentials"}), 401

    @app.post("/api/auth/verify")
    def auth_verify():
        """Проверка валидности токена."""
        token = request.cookies.get("auth_token")

        if token and verify_session_token(token):
            return jsonify({"authenticated": True})
        else:
            return jsonify({"authenticated": False}), 401

    @app.post("/api/auth/logout")
    def auth_logout():
        """Выход из системы."""
        response = jsonify({"success": True})
        response.set_cookie("auth_token", "", max_age=0)
        return response

    # ==================== Protected API ====================
    @app.post("/api/job")
    @require_auth
    def create_job():
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        session_id = payload.get("session_id") or request.cookies.get("auth_token")
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

        job = job_manager.create_job(url_list, check_options, runtime, session_id)
        return jsonify({"job_id": job.id})

    @app.get("/api/job/<job_id>")
    @require_auth
    def job_status(job_id: str):
        job = job_manager.get(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        snapshot = job_manager.status_snapshot(job)
        return jsonify(snapshot)

    @app.post("/api/job/<job_id>/stop")
    @require_auth
    def stop_job(job_id: str):
        ok = job_manager.stop(job_id)
        return jsonify({"stopped": ok}), (200 if ok else 404)

    @app.get("/api/job/<job_id>/log")
    @require_auth
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
            return (
                jsonify({"error": "log file not found (job may not have started yet)"}),
                404,
            )

        # Отдаём файл как текст
        try:
            return send_file(
                log_path,
                as_attachment=True,
                download_name=f"seo_{job_id}.log",
                mimetype="text/plain; charset=utf-8",
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @require_auth
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
    @require_auth
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
    @require_auth
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

    @app.post("/api/magic-links/job")
    @require_auth
    def create_magic_links_job():
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        session_id = payload.get("session_id") or request.cookies.get("auth_token")
        sources_raw = payload.get("sources", "")
        targets_raw = payload.get("targets", "")
        mode = payload.get("mode", "anchor")

        def normalize_lines(raw_text: str):
            lines = []
            for raw_line in str(raw_text).splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                lines.append(stripped)
            return lines

        source_list = normalize_lines(sources_raw)
        target_list = normalize_lines(targets_raw)
        max_len = max(len(source_list), len(target_list))
        pairs = []
        for idx in range(max_len):
            source = source_list[idx] if idx < len(source_list) else ""
            target = target_list[idx] if idx < len(target_list) else ""
            if source or target:
                pairs.append((source, target))

        if not pairs:
            return jsonify({"error": "Список ссылок пуст"}), 400

        if mode not in ("anchor", "alt"):
            return jsonify({"error": "Некорректный режим"}), 400

        if magic_links_manager.total_count_for_owner(session_id) >= 6:
            return jsonify({"error": "Достигнут лимит пар (6)"}), 400

        runtime_data = payload.get("runtime", {}) or {}
        try:
            concurrency = int(runtime_data.get("concurrency", 3))
        except (TypeError, ValueError):
            concurrency = 3
        try:
            timeout_seconds = int(runtime_data.get("timeout_seconds", 15))
        except (TypeError, ValueError):
            timeout_seconds = 15
        try:
            retries = int(runtime_data.get("retries", 2))
        except (TypeError, ValueError):
            retries = 2

        runtime = MagicLinksRuntime(
            concurrency=max(1, min(concurrency, 10)),
            timeout_seconds=max(3, min(timeout_seconds, 120)),
            retries=max(0, min(retries, 5)),
            delay_seconds=0.5,
        )

        job = magic_links_manager.create_job(session_id, pairs, mode, runtime)
        return jsonify({"job_id": job.id})

    @app.get("/api/magic-links/job/<job_id>")
    @require_auth
    def magic_links_job_status(job_id: str):
        job = magic_links_manager.get(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        snapshot = magic_links_manager.status_snapshot(job)
        return jsonify(snapshot)

    @app.post("/api/magic-links/job/<job_id>/stop")
    @require_auth
    def stop_magic_links_job(job_id: str):
        ok = magic_links_manager.stop(job_id)
        return jsonify({"stopped": ok}), (200 if ok else 404)

    @app.get("/api/magic-links/job/<job_id>/download-xlsx")
    @require_auth
    def download_magic_links_xlsx(job_id: str):
        data = magic_links_manager.results_xlsx_bytes(job_id)
        if data is None:
            return jsonify({"error": "not found"}), 404

        custom_filename = request.args.get("filename", "").strip()
        if custom_filename:
            safe_filename = "".join(
                c for c in custom_filename if c.isalnum() or c in ("-", "_", " ")
            )
            filename = (
                f"{safe_filename}.xlsx"
                if safe_filename
                else f"magic-links-{job_id}.xlsx"
            )
        else:
            filename = f"magic-links-{job_id}.xlsx"

        return send_file(
            io.BytesIO(data),
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.post("/api/google-speed/job")
    @require_auth
    def create_google_speed_job():
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        session_id = payload.get("session_id") or request.cookies.get("auth_token")

        raw_urls = payload.get("urls", "")
        url_list = [line.strip() for line in str(raw_urls).splitlines() if line.strip()]
        url_list = google_speed_manager.normalize_urls(url_list)
        if not url_list:
            return jsonify({"error": "Список URL пуст"}), 400

        api_key = str(payload.get("api_key", "")).strip()
        if not api_key:
            return jsonify({"error": "API-ключ обязателен"}), 400

        raw_strategies = payload.get("strategies", []) or []
        strategies = [
            item for item in raw_strategies if isinstance(item, str) and item in VALID_STRATEGIES
        ]
        if not strategies:
            return jsonify({"error": "Выберите хотя бы одну стратегию"}), 400

        raw_categories = payload.get("categories", []) or []
        categories = [
            item
            for item in raw_categories
            if isinstance(item, str) and item in VALID_CATEGORIES
        ]
        if not categories:
            return jsonify({"error": "Выберите хотя бы одну категорию"}), 400

        runtime_data = payload.get("runtime", {}) or {}
        try:
            concurrency = int(runtime_data.get("concurrency", 5))
        except (TypeError, ValueError):
            concurrency = 5

        runtime = GoogleSpeedRuntime(
            concurrency=max(1, min(concurrency, 10)),
            request_timeout_seconds=60,
            max_attempts_per_url=3,
            retry_delay_seconds=15,
        )

        job = google_speed_manager.create_job(
            owner_session=session_id,
            urls=url_list,
            api_key=api_key,
            strategies=strategies,
            categories=categories,
            runtime=runtime,
        )
        return jsonify({"job_id": job.id})

    @app.post("/api/google-speed/validate-key")
    @require_auth
    def validate_google_speed_key():
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        api_key = str(payload.get("api_key", "")).strip()
        if not api_key:
            return jsonify({"valid": False, "message": "API-ключ не указан"}), 400

        params = [
            ("url", "https://www.google.com"),
            ("key", api_key),
            ("strategy", "mobile"),
            ("category", "PERFORMANCE"),
        ]

        try:
            response = requests.get(PAGE_SPEED_ENDPOINT, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            lighthouse = data.get("lighthouseResult", {})
            categories = lighthouse.get("categories", {})
            has_score = categories.get("performance", {}).get("score") is not None
            if not has_score:
                return (
                    jsonify(
                        {
                            "valid": False,
                            "message": "Ключ принят, но score не получен (проверьте ограничения ключа)",
                        }
                    ),
                    400,
                )
            return jsonify({"valid": True, "message": "API-ключ валиден"})
        except requests.exceptions.HTTPError:
            error_msg = f"HTTP ошибка {response.status_code}"
            try:
                error_details = response.json()
                if "error" in error_details:
                    error_msg += f": {error_details['error'].get('message', '')}"
            except Exception:
                pass
            return jsonify({"valid": False, "message": error_msg}), 400
        except requests.exceptions.Timeout:
            return jsonify({"valid": False, "message": "Таймаут запроса"}), 400
        except requests.exceptions.RequestException as exc:
            return jsonify({"valid": False, "message": str(exc)}), 400
        except Exception as exc:
            return (
                jsonify({"valid": False, "message": f"Неожиданная ошибка: {str(exc)}"}),
                500,
            )

    @app.get("/api/google-speed/job/<job_id>")
    @require_auth
    def google_speed_job_status(job_id: str):
        job = google_speed_manager.get(job_id)
        if not job:
            return jsonify({"error": "not found"}), 404
        return jsonify(google_speed_manager.status_snapshot(job))

    @app.post("/api/google-speed/job/<job_id>/stop")
    @require_auth
    def stop_google_speed_job(job_id: str):
        ok = google_speed_manager.stop(job_id)
        return jsonify({"stopped": ok}), (200 if ok else 404)

    @app.get("/api/google-speed/job/<job_id>/download-xlsx")
    @require_auth
    def download_google_speed_xlsx(job_id: str):
        data = google_speed_manager.results_xlsx_bytes(job_id)
        if data is None:
            return jsonify({"error": "not found"}), 404

        custom_filename = request.args.get("filename", "").strip()
        if custom_filename:
            safe_filename = "".join(
                c for c in custom_filename if c.isalnum() or c in ("-", "_", " ")
            )
            filename = (
                f"{safe_filename}.xlsx"
                if safe_filename
                else f"google-speed-{job_id}.xlsx"
            )
        else:
            filename = f"google-speed-{job_id}.xlsx"

        return send_file(
            io.BytesIO(data),
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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

    @app.get("/api/stats")
    def get_stats():
        """Возвращает статистику: количество активных пользователей и очередь."""
        stats = job_manager.get_stats()
        magic_stats = magic_links_manager.get_stats()
        google_speed_stats = google_speed_manager.get_stats()
        stats["running"] += magic_stats["running"]
        stats["queued"] += magic_stats["queued"]
        stats["running"] += google_speed_stats["running"]
        stats["queued"] += google_speed_stats["queued"]
        return jsonify(stats)

    @app.post("/api/heartbeat")
    @require_auth
    def heartbeat():
        """Регистрирует heartbeat от активной вкладки."""
        payload = request.get_json(force=True, silent=True) or {}
        session_id = payload.get("session_id")
        if session_id:
            job_manager.heartbeat(session_id)
            return jsonify({"ok": True})
        return jsonify({"error": "session_id required"}), 400

    register_ssh_routes(app, require_auth)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
