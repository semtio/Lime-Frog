"""Замена текста в файлах с резервным копированием."""

import logging
from datetime import datetime
from typing import Tuple, Dict, List

from .ssh_client import SSHClient

logger = logging.getLogger(__name__)


class ReplaceTool:
    """Безопасная замена текста в файлах с бэкапом."""

    def __init__(self, ssh_client: SSHClient):
        """
        Args:
            ssh_client: Инициализированный SSH клиент
        """
        self.ssh = ssh_client

    def read_file(self, file_path: str) -> Tuple[bool, str]:
        """
        Прочитать содержимое файла через SFTP.

        Returns:
            (success, content)
        """
        try:
            content = self.ssh.read_file(file_path)
            return True, content
        except Exception as e:
            logger.error(f"[ReplaceTool] Error reading {file_path}: {e}")
            return False, f"Ошибка чтения файла: {str(e)}"

    def create_backup(self, file_path: str) -> Tuple[bool, str]:
        """
        Создать резервную копию файла через SFTP.

        Returns:
            (success, backup_path)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{file_path}.backup_{timestamp}"

        try:
            self.ssh.copy_file(file_path, backup_path)
            logger.info(f"[ReplaceTool] Backup created: {backup_path}")
            return True, backup_path
        except Exception as e:
            logger.error(f"[ReplaceTool] Error creating backup: {e}")
            return False, f"Ошибка создания бэкапа: {str(e)}"

    def preview_replacement(
        self,
        content: str,
        search_text: str,
        replace_text: str
    ) -> Tuple[bool, Dict]:
        """
        Показать предпросмотр замены без сохранения.
        Заменяет ВСЮ СТРОКУ, содержащую search_text, на replace_text.

        Returns:
            (success, preview_data)
            preview_data = {
                "found_count": int,
                "before": str,  # первая найденная строка
                "after": str,   # как она будет выглядеть после замены
            }
        """
        if search_text not in content:
            return False, {"error": f"Текст для поиска не найден в файле"}

        # Найти первую строку с search_text для предпросмотра
        lines = content.split('\n')
        first_match_line = None
        found_count = 0

        for line in lines:
            if search_text in line:
                if first_match_line is None:
                    first_match_line = line
                found_count += 1

        return True, {
            "found_count": found_count,
            "before": first_match_line,
            "after": replace_text,
            "will_replace_all": found_count > 1
        }

    def replace_in_file(
        self,
        file_path: str,
        search_text: str,
        replace_text: str,
        create_backup_flag: bool = True
    ) -> Tuple[bool, Dict]:
        """
        Выполнить замену текста в файле через SFTP.

        Args:
            file_path: Абсолютный путь до файла на сервере
            search_text: Текст для поиска
            replace_text: Текст для замены
            create_backup_flag: Создавать ли бэкап перед заменой

        Returns:
            (success, result_data)
            result_data = {
                "original_file": file_path,
                "backup_path": str or None,
                "replacements_count": int,
                "message": str,
            }
        """
        result = {
            "original_file": file_path,
            "backup_path": None,
            "replacements_count": 0,
            "message": ""
        }

        # Шаг 1: Прочитать файл
        success, content = self.read_file(file_path)
        if not success:
            logger.error(f"[ReplaceTool] Cannot read file: {file_path}")
            return False, {"error": content}

        # Шаг 2: Проверить, есть ли текст для поиска
        if search_text not in content:
            logger.warning(f"[ReplaceTool] Search text not found in {file_path}")
            return False, {"error": f"Текст для поиска не найден в файле"}

        # Шаг 3: Создать бэкап
        if create_backup_flag:
            success, backup_path = self.create_backup(file_path)
            if success:
                result["backup_path"] = backup_path
            else:
                logger.error(f"[ReplaceTool] Backup failed for {file_path}")
                return False, {"error": f"Не удалось создать бэкап: {backup_path}"}

        # Шаг 4: Выполнить замену ВСЕЙ СТРОКИ, содержащей search_text
        lines = content.split('\n')
        new_lines = []
        replacements_count = 0

        for line in lines:
            if search_text in line:
                # Заменить всю строку
                new_lines.append(replace_text)
                replacements_count += 1
                logger.debug(f"[ReplaceTool] Replaced line: '{line.strip()}' -> '{replace_text}'")
            else:
                new_lines.append(line)

        new_content = '\n'.join(new_lines)

        # Шаг 5: Записать файл обратно через SFTP
        try:
            self.ssh.write_file(file_path, new_content)
            result["replacements_count"] = replacements_count
            result["message"] = f"✓ Заменено {replacements_count} вхождений"
            logger.info(f"[ReplaceTool] Successfully replaced in {file_path}: {replacements_count} occurrences")
            return True, result
        except Exception as e:
            logger.error(f"[ReplaceTool] Error writing file {file_path}: {e}")
            # Откатить бэкап если есть
            if result["backup_path"]:
                try:
                    self.ssh.copy_file(result["backup_path"], file_path)
                    logger.info(f"[ReplaceTool] Restored from backup: {result['backup_path']}")
                except Exception as restore_error:
                    logger.error(f"[ReplaceTool] Failed to restore backup: {restore_error}")
            return False, {"error": f"Ошибка при записи файла: {str(e)}"}

    def batch_replace(
        self,
        files_list: List[Dict],
        search_text: str,
        replacements: Dict[str, str],
        create_backup_flag: bool = True
    ) -> Dict:
        """
        Выполнить замену для нескольких файлов одновременно.
        Каждый файл получает свою замену из словаря replacements.

        Args:
            files_list: Список файлов [{"domain": "...", "full_path": "..."}]
            search_text: Единый поисковый текст для всех файлов
            replacements: Словарь {domain: replace_text}
            create_backup_flag: Создавать ли бэкапы

        Returns:
            {
                "success_count": int,
                "error_count": int,
                "results": [
                    {"domain": "...", "status": "success|error", "message": "...", ...}
                ]
            }
        """
        results = {
            "success_count": 0,
            "error_count": 0,
            "results": []
        }

        for file_info in files_list:
            domain = file_info.get("domain", "unknown")
            full_path = file_info.get("full_path")
            replace_text = replacements.get(domain, "")

            if not replace_text:
                results["error_count"] += 1
                results["results"].append({
                    "domain": domain,
                    "status": "error",
                    "message": f"Нет текста для замены для домена {domain}"
                })
                continue

            # Выполнить замену
            success, result_data = self.replace_in_file(
                full_path,
                search_text,
                replace_text,
                create_backup_flag
            )

            if success:
                results["success_count"] += 1
                results["results"].append({
                    "domain": domain,
                    "status": "success",
                    "message": result_data.get("message", "OK"),
                    "backup_path": result_data.get("backup_path"),
                    "replacements_count": result_data.get("replacements_count", 0)
                })
            else:
                results["error_count"] += 1
                results["results"].append({
                    "domain": domain,
                    "status": "error",
                    "message": result_data.get("error", "Неизвестная ошибка")
                })

        return results
