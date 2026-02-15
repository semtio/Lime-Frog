"""
Backend логика аутентификации с использованием bcrypt.
"""

import json
import logging
import secrets
from pathlib import Path
from typing import Optional, Dict

import bcrypt

logger = logging.getLogger(__name__)

# Путь к файлу с учетными данными
CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"

# Хранилище активных сессий (в production лучше использовать Redis)
_active_sessions: Dict[str, bool] = {}


def _load_credentials() -> Dict[str, str]:
    """Загружает хешированные учетные данные из JSON файла."""
    try:
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "username_hash": data.get("username_hash", ""),
                "password_hash": data.get("password_hash", ""),
            }
    except FileNotFoundError:
        logger.error(f"Файл credentials.json не найден: {CREDENTIALS_FILE}")
        return {"username_hash": "", "password_hash": ""}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга credentials.json: {e}")
        return {"username_hash": "", "password_hash": ""}


def hash_value(value: str) -> str:
    """
    Хеширует значение с использованием bcrypt.

    Args:
        value: Строка для хеширования (логин или пароль)

    Returns:
        Bcrypt хеш в виде строки
    """
    return bcrypt.hashpw(value.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_hash(value: str, hash_str: str) -> bool:
    """
    Проверяет соответствие значения хешу.

    Args:
        value: Исходная строка (логин или пароль)
        hash_str: Bcrypt хеш для сравнения

    Returns:
        True если значение соответствует хешу
    """
    try:
        return bcrypt.checkpw(value.encode("utf-8"), hash_str.encode("utf-8"))
    except Exception as e:
        logger.error(f"Ошибка проверки хеша: {e}")
        return False


def verify_credentials(username: str, password: str) -> bool:
    """
    Проверяет учетные данные пользователя.

    Args:
        username: Логин пользователя
        password: Пароль пользователя

    Returns:
        True если учетные данные верны
    """
    if not username or not password:
        return False

    creds = _load_credentials()
    username_hash = creds.get("username_hash", "")
    password_hash = creds.get("password_hash", "")

    # Проверяем что хеши не пустые и не являются placeholder'ами
    if not username_hash or not password_hash:
        logger.warning("Учетные данные не настроены в credentials.json")
        return False

    if "ВСТАВЬТЕ_СЮДА" in username_hash or "ВСТАВЬТЕ_СЮДА" in password_hash:
        logger.warning("Учетные данные в credentials.json не заполнены")
        return False

    # Проверяем логин и пароль
    username_valid = _verify_hash(username, username_hash)
    password_valid = _verify_hash(password, password_hash)

    return username_valid and password_valid


def create_session_token() -> str:
    """
    Создает безопасный токен сессии.

    Returns:
        Уникальный токен сессии (hex строка)
    """
    token = secrets.token_hex(32)  # 64 символа
    _active_sessions[token] = True
    logger.info(f"Создан новый токен сессии: {token[:8]}...")
    return token


def verify_session_token(token: str) -> bool:
    """
    Проверяет валидность токена сессии.

    Args:
        token: Токен сессии для проверки

    Returns:
        True если токен валиден
    """
    return token in _active_sessions


def invalidate_session_token(token: str) -> None:
    """
    Инвалидирует токен сессии (logout).

    Args:
        token: Токен для инвалидации
    """
    if token in _active_sessions:
        del _active_sessions[token]
        logger.info(f"Токен сессии инвалидирован: {token[:8]}...")
