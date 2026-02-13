"""
Конфигурация логирования для Lime-Frog SEO Checker.

Структура логов:
- logs/app.log - общий application лог (с ротацией)
- logs/seo_<job_id>.log - логи конкретных job'ов (TTL 14 дней или max 100 файлов)
"""

import glob
import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Директория для логов (абсолютный путь от корня проекта)
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_DIR = PROJECT_ROOT / "logs"
APP_LOG_FILE = LOG_DIR / "app.log"
SEO_JOB_LOG_PATTERN = "seo_*.log"

# Политика хранения job-логов
MAX_JOB_LOG_AGE_DAYS = 14
MAX_JOB_LOG_COUNT = 100

# Убедиться что директория существует
LOG_DIR.mkdir(exist_ok=True)


def mask_sensitive_url(url: str) -> str:
    """
    Маскирует чувствительные данные в URL для безопасного логирования.

    Заменяет:
    - user:pass@ → ***:***@
    - token=xxx, key=xxx, signature=xxx, api_key=xxx → param=***

    Args:
        url: URL который нужно замаскировать

    Returns:
        URL с замаскированными чувствительными данными
    """
    if not url:
        return url

    # Маскировка basic auth (user:pass@)
    masked = re.sub(
        r'://(([^:@]+):([^@]+)@)',
        r'://***:***@',
        url
    )

    # Маскировка чувствительных query параметров
    sensitive_params = [
        'token', 'key', 'api_key', 'apikey', 'signature', 'sig',
        'secret', 'password', 'passwd', 'pwd', 'access_token',
        'refresh_token', 'auth', 'authorization'
    ]

    for param in sensitive_params:
        # Маскируем param=value (до & или конца строки)
        masked = re.sub(
            rf'({param}=)[^&\s]+',
            r'\1***',
            masked,
            flags=re.IGNORECASE
        )

    return masked


def setup_logging():
    """
    Настройка логирования приложения.

    Создаёт:
    - RotatingFileHandler для logs/app.log (10MB × 5 файлов)
    - StreamHandler для stdout (для journalctl)
    """
    logger = logging.getLogger("lime_frog")
    logger.setLevel(logging.INFO)

    # Очистить старые handlers если есть
    logger.handlers.clear()

    # Ротируемый файл для application логов
    file_handler = RotatingFileHandler(
        APP_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )

    # Формат: timestamp | level | module | message
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Дублируем в stdout для journalctl
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(file_formatter)
    logger.addHandler(console_handler)

    logger.info("Logging configured: app.log + stdout")

    return logger


def get_job_log_path(job_id: str) -> Path:
    """Возвращает путь к log-файлу для конкретного job."""
    return LOG_DIR / f"seo_{job_id}.log"


def create_job_logger(job_id: str) -> logging.Logger:
    """
    Создаёт отдельный logger для конкретного job с FileHandler.

    ВАЖНО: После завершения job нужно вызвать cleanup_job_logger(job_id)
    чтобы закрыть handler и избежать утечки дескрипторов.

    Args:
        job_id: Уникальный идентификатор job

    Returns:
        Logger с настроенным FileHandler для logs/seo_<job_id>.log
    """
    logger_name = f"lime_frog.job.{job_id}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Не отправлять в root logger

    # Очистить старые handlers если есть
    logger.handlers.clear()

    # FileHandler для job-specific лога
    job_log_path = get_job_log_path(job_id)
    file_handler = logging.FileHandler(job_log_path, mode='w', encoding='utf-8')

    # Формат: timestamp | level | job_id | message
    formatter = logging.Formatter(
        f'%(asctime)s | %(levelname)-8s | {job_id} | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def cleanup_job_logger(job_id: str):
    """
    Отцепляет и закрывает все handlers для job logger.

    ОБЯЗАТЕЛЬНО вызывать после завершения job (success/error/stopped)
    чтобы не было утечки file descriptors.

    Args:
        job_id: Уникальный идентификатор job
    """
    logger_name = f"lime_frog.job.{job_id}"
    logger = logging.getLogger(logger_name)

    # Закрыть и удалить все handlers
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def cleanup_old_job_logs(max_age_days: int = MAX_JOB_LOG_AGE_DAYS,
                         max_count: int = MAX_JOB_LOG_COUNT):
    """
    Очистка старых job-логов по политике хранения:
    1. Удаляются файлы старше max_age_days (по умолчанию 14 дней)
    2. Если файлов больше max_count, удаляются самые старые

    Args:
        max_age_days: Максимальный возраст файла в днях
        max_count: Максимальное количество файлов
    """
    log_files = list(LOG_DIR.glob(SEO_JOB_LOG_PATTERN))

    if not log_files:
        return

    # Сортируем по времени модификации (старые первыми)
    log_files_sorted = sorted(log_files, key=lambda f: f.stat().st_mtime)

    # 1. Удаляем файлы старше max_age_days
    cutoff_time = time.time() - (max_age_days * 86400)
    deleted_by_age = 0

    for log_file in log_files_sorted[:]:
        try:
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                log_files_sorted.remove(log_file)
                deleted_by_age += 1
        except OSError:
            pass  # Файл уже удалён или недоступен

    # 2. Если осталось больше max_count, удаляем самые старые
    deleted_by_count = 0
    if len(log_files_sorted) > max_count:
        for old_file in log_files_sorted[:-max_count]:
            try:
                old_file.unlink()
                deleted_by_count += 1
            except OSError:
                pass

    # Логируем результат очистки
    if deleted_by_age > 0 or deleted_by_count > 0:
        logger = logging.getLogger("lime_frog")
        logger.info(
            f"Cleanup job logs: removed {deleted_by_age} old files (>{max_age_days}d), "
            f"{deleted_by_count} excess files (max={max_count})"
        )
