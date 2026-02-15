"""Хранилище SSH серверов (зашифрованные логины/пароли)."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from .encryption import encrypt_value, decrypt_value


_DATA_DIR = Path(__file__).parent / "data"
_SERVERS_FILE = _DATA_DIR / "servers.json"


def _ensure_storage() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not _SERVERS_FILE.exists():
        _SERVERS_FILE.write_text("{\n  \"servers\": []\n}\n", encoding="utf-8")


def _load_data() -> Dict[str, List[Dict[str, str]]]:
    _ensure_storage()
    with open(_SERVERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_data(data: Dict[str, List[Dict[str, str]]]) -> None:
    _ensure_storage()
    with open(_SERVERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_servers() -> List[Dict[str, str]]:
    data = _load_data()
    result = []
    for server in data.get("servers", []):
        result.append(
            {
                "id": server["id"],
                "name": server.get("name", ""),
                "host": server.get("host", ""),
                "port": server.get("port", 22),
                "created_at": server.get("created_at", ""),
                "updated_at": server.get("updated_at", ""),
            }
        )
    return result


def add_server(
    name: str,
    host: str,
    username: str,
    password: str,
    port: int = 22,
) -> Dict[str, str]:
    data = _load_data()
    server_id = str(uuid4())
    now = _now_iso()

    server = {
        "id": server_id,
        "name": name,
        "host": host,
        "port": int(port),
        "username_enc": encrypt_value(username),
        "password_enc": encrypt_value(password),
        "created_at": now,
        "updated_at": now,
    }
    data.setdefault("servers", []).append(server)
    _save_data(data)

    return {
        "id": server_id,
        "name": name,
        "host": host,
        "port": int(port),
        "created_at": now,
        "updated_at": now,
    }


def delete_server(server_id: str) -> bool:
    data = _load_data()
    servers = data.get("servers", [])
    new_servers = [s for s in servers if s.get("id") != server_id]
    if len(new_servers) == len(servers):
        return False
    data["servers"] = new_servers
    _save_data(data)
    return True


def get_server(server_id: str) -> Optional[Dict[str, str]]:
    data = _load_data()
    for server in data.get("servers", []):
        if server.get("id") == server_id:
            return {
                "id": server_id,
                "name": server.get("name", ""),
                "host": server.get("host", ""),
                "port": int(server.get("port", 22)),
                "username": decrypt_value(server.get("username_enc", "")),
                "password": decrypt_value(server.get("password_enc", "")),
                "base_path": server.get("base_path", ""),
            }
    return None


def update_server_base_path(server_id: str, base_path: str) -> bool:
    """Обновить base_path для сервера."""
    data = _load_data()
    for server in data.get("servers", []):
        if server.get("id") == server_id:
            server["base_path"] = base_path
            server["updated_at"] = _now_iso()
            _save_data(data)
            return True
    return False
