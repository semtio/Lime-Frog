"""Замена текста в файлах."""

import logging
import shlex
import uuid
from typing import Tuple, Dict, List

from .ssh_client import SSHClient

logger = logging.getLogger(__name__)


class ReplaceTool:
    """Замена текста в файлах через SSH exec."""

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

    def preview_replacement(
        self, content: str, search_text: str, replace_text: str
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
        lines = content.split("\n")
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
            "will_replace_all": found_count > 1,
        }

    def replace_in_file(
        self, file_path: str, search_text: str, replace_text: str
    ) -> Tuple[bool, Dict]:
        """
        Выполнить замену текста в файле через exec (PTY).

        Args:
            file_path: Абсолютный путь до файла на сервере
            search_text: Текст для поиска
            replace_text: Текст для замены

        Returns:
            (success, result_data)
            result_data = {
                "original_file": file_path,
                "replacements_count": int,
                "message": str,
            }
        """
        result = {"original_file": file_path, "replacements_count": 0, "message": ""}

        file_q = shlex.quote(file_path)
        search_q = shlex.quote(search_text)
        replace_q = shlex.quote(replace_text)

        # Шаг 1: Диагностика контекста выполнения перед записью
        diagnostics_output = ""
        try:
            diagnostics_output = self.ssh.get_diagnostics(file_path)
        except Exception as diag_err:
            logger.warning(
                f"[ReplaceTool] Diagnostics failed for {file_path}: {diag_err}"
            )

        # Шаг 2: Проверить количество совпадений через exec
        try:
            count_cmd = f"grep -F -c -- {search_q} {file_q} || true"
            count_out = self.ssh.execute(count_cmd, get_pty=True)
            replacements_count = int(count_out.strip() or 0)
        except Exception as e:
            logger.error(f"[ReplaceTool] Count failed for {file_path}: {e}")
            return False, {"error": f"Ошибка проверки совпадений: {str(e)}"}

        if replacements_count == 0:
            logger.warning(f"[ReplaceTool] Search text not found in {file_path}")
            return False, {"error": f"Текст для поиска не найден в файле"}

        # Шаг 3: Заменить все строки с search_text через exec
        owner_hint = ""
        tmp_path = f"{file_path}.tmp.{uuid.uuid4().hex}"
        tmp_q = shlex.quote(tmp_path)
        awk_program = 'index($0,s){ if (r!="") print r; next } {print}'
        cmd = (
            f"orig={file_q}; tmp={tmp_q}; "
            f'awk -v s={search_q} -v r={replace_q} \'{awk_program}\' "$orig" > "$tmp"; '
            'status=$?; if [ $status -ne 0 ]; then rm -f "$tmp"; exit $status; fi; '
            'mode=$(stat -c %a "$orig" 2>/dev/null || true); '
            'uid=$(stat -c %u "$orig" 2>/dev/null || true); '
            'gid=$(stat -c %g "$orig" 2>/dev/null || true); '
            'if [ -n "$mode" ]; then chmod "$mode" "$tmp" 2>/dev/null || true; fi; '
            'if [ -n "$uid" ] && [ -n "$gid" ]; then chown "$uid:$gid" "$tmp" 2>/dev/null || true; fi; '
            'mv "$tmp" "$orig"'
        )

        try:
            _out, err, status = self.ssh.execute_raw(
                cmd, get_pty=True, log_output=False
            )
            if status != 0:
                raise Exception(err or "replace failed")

            result["replacements_count"] = replacements_count
            result["message"] = f"✓ Заменено {replacements_count} вхождений"
            logger.info(
                f"[ReplaceTool] Successfully replaced in {file_path}: {replacements_count} occurrences"
            )
            return True, result
        except Exception as e:
            logger.error(f"[ReplaceTool] Error writing file {file_path}: {e}")
            try:
                owner_info = self.ssh.get_file_owner(file_path)
                owner_hint = (
                    f" (UID={owner_info.get('uid')}, GID={owner_info.get('gid')}, "
                    f"Mode={owner_info.get('mode')})"
                )
            except Exception:
                owner_hint = ""
            diagnostics_hint = (
                f"\nContext:\n{diagnostics_output}" if diagnostics_output else ""
            )
            return False, {
                "error": f"Ошибка при записи файла: {str(e)}{owner_hint}{diagnostics_hint}"
            }

    def batch_replace(
        self,
        files_list: List[Dict],
        search_text: str,
        replacements: Dict[str, str],
        create_backup_flag: bool = True,
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
        results = {"success_count": 0, "error_count": 0, "results": []}

        for file_info in files_list:
            domain = file_info.get("domain", "unknown")
            full_path = file_info.get("full_path")
            replace_text = replacements.get(domain, "")

            if not replace_text:
                results["error_count"] += 1
                results["results"].append(
                    {
                        "domain": domain,
                        "status": "error",
                        "message": f"Нет текста для замены для домена {domain}",
                    }
                )
                continue

            # Выполнить замену
            success, result_data = self.replace_in_file(
                full_path, search_text, replace_text
            )

            if success:
                results["success_count"] += 1
                results["results"].append(
                    {
                        "domain": domain,
                        "status": "success",
                        "message": result_data.get("message", "OK"),
                        "backup_path": result_data.get("backup_path"),
                        "replacements_count": result_data.get("replacements_count", 0),
                    }
                )
            else:
                results["error_count"] += 1
                results["results"].append(
                    {
                        "domain": domain,
                        "status": "error",
                        "message": result_data.get("error", "Неизвестная ошибка"),
                    }
                )

        return results
