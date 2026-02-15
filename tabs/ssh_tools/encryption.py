"""Шифрование данных SSH Tools (пароли и логины)."""

import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet


_DATA_DIR = Path(__file__).parent / "data"
_KEY_FILE = _DATA_DIR / "ssh_tools.key"
_FERNET: Optional[Fernet] = None


def _load_or_create_key() -> bytes:
    env_key = os.environ.get("SSH_TOOLS_KEY", "").strip()
    if env_key:
        return env_key.encode("utf-8")

    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()

    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


def get_fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        key = _load_or_create_key()
        _FERNET = Fernet(key)
    return _FERNET


def encrypt_value(value: str) -> str:
    fernet = get_fernet()
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_value(token: str) -> str:
    fernet = get_fernet()
    value = fernet.decrypt(token.encode("utf-8"))
    return value.decode("utf-8")
