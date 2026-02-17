"""Routes для SSH Tools."""

import logging
from flask import jsonify, request, send_from_directory
from pathlib import Path

logger = logging.getLogger(__name__)

from .servers import (
    add_server,
    delete_server,
    get_server,
    list_servers,
    update_server,
    update_server_base_path,
)
from .ssh_client import test_connection, SSHClient
from .file_finder import FileFinder
from .replace_tool import ReplaceTool


def register_routes(app, require_auth):
    """Регистрация маршрутов для SSH Tools."""

    def _connect_ssh(server: dict) -> tuple[SSHClient | None, str, str | None]:
        host = server["host"]
        port = server["port"]
        stored_username = server.get("username", "")
        password = server.get("password", "")

        if stored_username and stored_username != "root":
            root_client = SSHClient(host, port, "root", password)
            success, message = root_client.connect()
            if success:
                return root_client, "root", None
            root_client.close()
            logger.warning(
                "[SSH] Root login failed for %s: %s",
                host,
                message,
            )

        ssh = SSHClient(host, port, stored_username, password)
        success, message = ssh.connect()
        if success:
            return ssh, stored_username, None
        return None, stored_username, message

    static_dir = Path(__file__).parent / "static"

    @app.get("/ssh-tools/static/<path:filename>")
    def ssh_tools_static(filename: str):
        return send_from_directory(static_dir, filename)

    @app.get("/api/ssh-tools/servers")
    @require_auth
    def ssh_list_servers():
        return jsonify({"servers": list_servers()})

    @app.post("/api/ssh-tools/servers")
    @require_auth
    def ssh_add_server():
        payload = request.get_json(force=True, silent=True) or {}
        name = str(payload.get("name", "")).strip()
        host = str(payload.get("host", "")).strip()
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        port = payload.get("port", 22)

        if not name or not host or not username or not password:
            return jsonify({"error": "name, host, username, password required"}), 400

        try:
            port = int(port)
        except (TypeError, ValueError):
            return jsonify({"error": "port must be a number"}), 400

        server = add_server(name, host, username, password, port)
        return jsonify(server), 201

    @app.get("/api/ssh-tools/servers/<server_id>")
    @require_auth
    def ssh_get_server(server_id: str):
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404
        return jsonify(server), 200

    @app.put("/api/ssh-tools/servers/<server_id>")
    @require_auth
    def ssh_update_server(server_id: str):
        payload = request.get_json(force=True, silent=True) or {}
        name = str(payload.get("name", "")).strip()
        host = str(payload.get("host", "")).strip()
        username = str(payload.get("username", "")).strip()
        password = str(payload.get("password", "")).strip()
        port = payload.get("port", 22)

        if not name or not host or not username or not password:
            return jsonify({"error": "name, host, username, password required"}), 400

        try:
            port = int(port)
        except (TypeError, ValueError):
            return jsonify({"error": "port must be a number"}), 400

        ok = update_server(server_id, name, host, username, password, port)
        if not ok:
            return jsonify({"error": "server not found"}), 404

        return jsonify({"ok": True}), 200

    @app.delete("/api/ssh-tools/servers/<server_id>")
    @require_auth
    def ssh_delete_server(server_id: str):
        ok = delete_server(server_id)
        if not ok:
            return jsonify({"error": "server not found"}), 404
        return jsonify({"ok": True})

    @app.post("/api/ssh-tools/servers/<server_id>/test")
    @require_auth
    def ssh_test_server(server_id: str):
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        ssh, username, error = _connect_ssh(server)
        if not ssh:
            return jsonify({"ok": False, "message": f"Ошибка подключения: {error}"})
        ssh.close()
        return jsonify(
            {"ok": True, "message": f"Подключение успешно (user: {username})"}
        )

    @app.post("/api/ssh-tools/servers/<server_id>/exec")
    @require_auth
    def ssh_exec_command(server_id: str):
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        payload = request.get_json(force=True, silent=True) or {}
        command_text = payload.get("command", "")
        if not isinstance(command_text, str) or not command_text.strip():
            return jsonify({"error": "command required"}), 400

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500

            script = command_text.rstrip() + "\n"
            stdout, stderr, exit_code = ssh.execute_raw(
                "bash -s",
                get_pty=True,
                stdin_bytes=script.encode("utf-8"),
                log_output=False,
            )
            ssh.close()

            return jsonify(
                {
                    "ok": exit_code == 0,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/ssh-tools/servers/<server_id>/home-paths")
    @require_auth
    def ssh_home_paths(server_id: str):
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500

            cmd = "ls -1d /home/*/web 2>/dev/null | sort"
            output = ssh.execute(cmd, get_pty=True)
            ssh.close()

            paths = [line.strip() for line in output.split("\n") if line.strip()]
            return jsonify({"ok": True, "paths": paths})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/ssh-tools/servers/<server_id>/set-base-path")
    @require_auth
    def ssh_set_base_path(server_id: str):
        """Установить и проверить base_path для поиска доменов."""
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        payload = request.get_json(force=True, silent=True) or {}
        base_path = str(payload.get("base_path", "")).strip()

        if not base_path:
            return jsonify({"error": "base_path required"}), 400

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500

            finder = FileFinder(ssh)
            success, message = finder.verify_and_set_base_path(base_path)

            if success:
                # Сохранить base_path в БД
                update_server_base_path(server_id, base_path)
                ssh.close()
                return jsonify({"ok": True, "message": message, "base_path": base_path})
            else:
                ssh.close()
                return jsonify({"ok": False, "error": message}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.get("/api/ssh-tools/servers/<server_id>/find-files")
    @require_auth
    def ssh_find_files(server_id: str):
        """Найти файлы по относительному пути во всех доменах."""
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        base_path = server.get("base_path")
        if not base_path:
            return jsonify({"error": "base_path not set for this server"}), 400

        relative_path = request.args.get("relative_path", "").strip()
        if not relative_path:
            return jsonify({"error": "relative_path required"}), 400

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500

            finder = FileFinder(ssh)
            success, files_list = finder.find_files_by_pattern(base_path, relative_path)

            ssh.close()

            if success:
                return jsonify({"ok": True, "files": files_list})
            else:
                return jsonify({"ok": False, "files": files_list}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/ssh-tools/servers/<server_id>/validate-paths")
    @require_auth
    def ssh_validate_paths(server_id: str):
        """Проверить, какие из указанных путей существуют на сервере."""
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        payload = request.get_json(force=True, silent=True) or {}
        paths = payload.get("paths", [])

        if not paths:
            return jsonify({"error": "paths required"}), 400

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500

            found = []
            not_found = []

            # Проверить каждый путь
            for path in paths:
                path = str(path).strip()
                if not path:
                    continue

                exists = ssh.path_exists(path)
                if exists:
                    found.append(path)
                    # Установить права 777 сразу при валидации
                    try:
                        ssh.chmod(path, 0o777)
                        logger.info(f"[ValidatePaths] Set 777 permissions for {path}")
                    except Exception as chmod_err:
                        logger.warning(
                            f"[ValidatePaths] Could not chmod {path}: {chmod_err}"
                        )
                        # Продолжаем работу даже если chmod не удался
                else:
                    not_found.append(path)

            # Закрыть соединение
            ssh.close()

            return jsonify(
                {
                    "ok": True,
                    "found": found,
                    "not_found": not_found,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/ssh-tools/servers/<server_id>/preview-replace")
    @require_auth
    def ssh_preview_replace(server_id: str):
        """Показать предпросмотр замены текста в файле."""
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        payload = request.get_json(force=True, silent=True) or {}
        file_path = str(payload.get("file_path", "")).strip()
        search_text = str(payload.get("search_text", ""))
        replace_text = str(payload.get("replace_text", ""))

        if not file_path or not search_text:
            return jsonify({"error": "file_path and search_text required"}), 400

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500
            tool = ReplaceTool(ssh)

            # Прочитать файл
            success, content = tool.read_file(file_path)
            if not success:
                return jsonify({"error": content}), 400

            # Показать предпросмотр
            success, preview = tool.preview_replacement(
                content, search_text, replace_text
            )
            if success:
                return jsonify({"ok": True, "preview": preview})
            else:
                return jsonify({"ok": False, "error": preview.get("error")}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.post("/api/ssh-tools/servers/<server_id>/execute-replace")
    @require_auth
    def ssh_execute_replace(server_id: str):
        """Выполнить замену текста в файлах."""
        server = get_server(server_id)
        if not server:
            return jsonify({"error": "server not found"}), 404

        payload = request.get_json(force=True, silent=True) or {}
        files_list = payload.get("files", [])
        search_text = str(payload.get("search_text", ""))

        if not files_list or not search_text:
            return jsonify({"error": "files and search_text required"}), 400

        # Извлечь полные пути и замены из объектов файлов
        file_operations = []
        for f in files_list:
            if isinstance(f, dict):
                path = f.get("full_path")
                replace_text = f.get("replace_text", "")
                if path:  # Разрешаем пустой replace_text для удаления строк
                    file_operations.append({"path": path, "replace_text": replace_text})

        if not file_operations:
            return jsonify({"error": "no valid file operations provided"}), 400

        try:
            ssh, _, error = _connect_ssh(server)
            if not ssh:
                return jsonify({"error": f"Не удалось подключиться: {error}"}), 500

            tool = ReplaceTool(ssh)

            # Выполнить замену для каждого файла
            results = []
            success_count = 0
            error_count = 0

            for operation in file_operations:
                file_path = operation["path"]
                replace_text = operation["replace_text"]

                success, result_data = tool.replace_in_file(
                    file_path, search_text, replace_text
                )

                if success:
                    results.append(
                        {
                            "path": file_path,
                            "status": "success",
                            "message": result_data.get(
                                "message", "✓ Замена успешно выполнена"
                            ),
                            "replacements_count": result_data.get(
                                "replacements_count", 0
                            ),
                        }
                    )
                    success_count += 1
                else:
                    results.append(
                        {
                            "path": file_path,
                            "status": "error",
                            "message": result_data.get("error", "Ошибка замены"),
                        }
                    )
                    error_count += 1

            # Закрыть соединение
            ssh.close()

            return jsonify(
                {
                    "ok": error_count == 0,
                    "success_count": success_count,
                    "error_count": error_count,
                    "details": results,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return None
