"""Поиск доменов и файлов на удалённом сервере по SSH."""

import logging
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from .ssh_client import SSHClient

logger = logging.getLogger(__name__)


class FileFinder:
    """Умный поиск доменов и файлов на сервере."""

    def __init__(self, ssh_client: SSHClient):
        """
        Args:
            ssh_client: Инициализированный SSH клиент
        """
        self.ssh = ssh_client

    def verify_and_set_base_path(self, base_path: str) -> Tuple[bool, str]:
        """
        Проверить, существует ли base_path на сервере и сохранить его.

        Args:
            base_path: Абсолютный путь до папки с доменами (например: /home/admin/web/)

        Returns:
            (success, message)
        """
        # Убрать trailing slash для консистентности
        base_path = base_path.rstrip('/')
        logger.info(f"[FileFinder] Verifying base_path: {base_path}")

        # Проверить существование через SFTP
        try:
            exists = self.ssh.path_exists(base_path)
            if exists:
                logger.info(f"[FileFinder] Path verified successfully: {base_path}")
                return True, f"Путь подтверждён: {base_path}"
            else:
                logger.warning(f"[FileFinder] Path not found: {base_path}")
                return False, f"Путь не найден на сервере: {base_path}"
        except Exception as e:
            logger.error(f"[FileFinder] Verification error: {str(e)}")
            return False, f"Ошибка проверки пути: {str(e)}"

    def scan_domains(self, base_path: str) -> Dict[str, Dict]:
        """
        Сканировать доменов в base_path.
        Возвращает структуру: {domain_name: {base_dir, files}}

        Args:
            base_path: Базовый путь до папки с доменами

        Returns:
            Словарь найденных доменов с их файлами
        """
        base_path = base_path.rstrip('/')
        domains = {}

        # Поиск всех папок в base_path (это домены)
        cmd = f'find "{base_path}" -maxdepth 1 -type d ! -name ".*" | sort'
        try:
            result = self.ssh.execute(cmd)
            domain_dirs = [d.strip() for d in result.split('\n') if d.strip() and d.strip() != base_path]
        except Exception as e:
            return {"error": f"Ошибка сканирования доменов: {str(e)}"}

        # Для каждого домена найти .php и .html файлы
        for domain_dir in domain_dirs:
            domain_name = os.path.basename(domain_dir)

            # Поиск файлов рекурсивно
            cmd = f'find "{domain_dir}" -type f \\( -name "*.php" -o -name "*.html" \\) ! -path "*/.*" | sort'
            try:
                result = self.ssh.execute(cmd)
                files = [f.strip() for f in result.split('\n') if f.strip()]

                # Преобразовать абсолютные пути в относительные от base_path
                relative_files = []
                for f in files:
                    try:
                        rel_path = f.replace(domain_dir + '/', '')
                        relative_files.append(rel_path)
                    except:
                        pass

                if relative_files:
                    domains[domain_name] = {
                        "base_dir": domain_dir,
                        "files": relative_files
                    }
            except Exception as e:
                # Пропустить ошибочный домен, не прерывать сканирование
                continue

        return domains

    def find_files_by_pattern(self, base_path: str, relative_path: str) -> Tuple[bool, List[Dict]]:
        """
        Найти все файлы по относительному пути во всех доменах.
        Например: relative_path = "public_html/header.php"

        Args:
            base_path: Базовый путь до папки с доменами
            relative_path: Относительный путь от корня домена

        Returns:
            (success, files_list)
            files_list = [
                {"domain": "domain1.com", "full_path": "/home/admin/web/domain1.com/public_html/header.php"},
                ...
            ]
        """
        base_path = base_path.rstrip('/')
        relative_path = relative_path.lstrip('/')

        found_files = []

        # Получить список доменов через SFTP
        try:
            domain_dirs = self.ssh.list_directories(base_path)
        except Exception as e:
            logger.error(f"[FileFinder] Error listing domains in {base_path}: {e}")
            return False, [{"error": f"Ошибка сканирования: {str(e)}"}]

        logger.info(f"[FileFinder] Found {len(domain_dirs)} domains in {base_path}")

        # Для каждого домена проверить, существует ли файл
        for domain_name in domain_dirs:
            full_path = f"{base_path}/{domain_name}/{relative_path}"

            # Проверить существование файла через SFTP
            if self.ssh.path_exists(full_path):
                found_files.append({
                    "domain": domain_name,
                    "full_path": full_path,
                    "relative_path": relative_path
                })
                logger.info(f"[FileFinder] Found file: {full_path}")

        if not found_files:
            logger.warning(f"[FileFinder] File not found in any domain: {relative_path}")
            return False, [{"error": f"Файл не найден ни в одном домене: {relative_path}"}]

        logger.info(f"[FileFinder] Total files found: {len(found_files)}")
        return True, found_files
