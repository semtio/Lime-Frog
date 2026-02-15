"""Routes для SSH Tools."""

from flask import jsonify, request, send_from_directory
from pathlib import Path

from .servers import add_server, delete_server, get_server, list_servers, update_server_base_path
from .ssh_client import test_connection, SSHClient
from .file_finder import FileFinder
from .replace_tool import ReplaceTool


def register_routes(app, require_auth):
    """Регистрация маршрутов для SSH Tools."""

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

        ok, message = test_connection(
            server["host"],
            server["port"],
            server["username"],
            server["password"],
        )
        return jsonify({"ok": ok, "message": message})

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
            ssh = SSHClient(
                server["host"],
                server["port"],
                server["username"],
                server["password"],
            )

            # Явно установить соединение
            success, message = ssh.connect()
            if not success:
                return jsonify({"error": f"Не удалось подключиться: {message}"}), 500

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
            ssh = SSHClient(
                server["host"],
                server["port"],
                server["username"],
                server["password"],
            )

            # Явно установить соединение
            success, message = ssh.connect()
            if not success:
                return jsonify({"error": f"Не удалось подключиться: {message}"}), 500

            finder = FileFinder(ssh)
            success, files_list = finder.find_files_by_pattern(base_path, relative_path)

            ssh.close()

            if success:
                return jsonify({"ok": True, "files": files_list})
            else:
                return jsonify({"ok": False, "files": files_list}), 400
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
            ssh = SSHClient(
                server["host"],
                server["port"],
                server["username"],
                server["password"],
            )
            tool = ReplaceTool(ssh)

            # Прочитать файл
            success, content = tool.read_file(file_path)
            if not success:
                return jsonify({"error": content}), 400

            # Показать предпросмотр
            success, preview = tool.preview_replacement(content, search_text, replace_text)
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
        replacements = payload.get("replacements", {})  # {domain: replace_text}

        if not files_list or not search_text or not replacements:
            return jsonify({"error": "files, search_text, replacements required"}), 400

        try:
            ssh = SSHClient(
                server["host"],
                server["port"],
                server["username"],
                server["password"],
            )

            # Явно установить соединение
            success, message = ssh.connect()
            if not success:
                return jsonify({"error": f"Не удалось подключиться: {message}"}), 500

            tool = ReplaceTool(ssh)

            # Выполнить batch замену
            results = tool.batch_replace(files_list, search_text, replacements)

            # Закрыть соединение
            ssh.close()

            return jsonify({
                "ok": results["error_count"] == 0,
                "success_count": results["success_count"],
                "error_count": results["error_count"],
                "details": results["results"]
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return None
