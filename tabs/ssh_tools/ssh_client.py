"""SSH клиент для тестового подключения."""

import logging
import shlex
from typing import Tuple, List
import stat

import paramiko

logger = logging.getLogger(__name__)


class SSHClient:
    """Обёртка для SSH/SFTP подключения и выполнения команд."""

    def __init__(self, host: str, port: int, username: str, password: str):
        """
        Args:
            host: IP или домен сервера
            port: Порт SSH (по умолчанию 22)
            username: Логин
            password: Пароль
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.sftp = None

    def connect(self) -> Tuple[bool, str]:
        """Установить SSH подключение."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=30,
                auth_timeout=30,
                banner_timeout=30,
            )
            logger.info(f"[SSH] Connected to {self.host} as user '{self.username}'")
            return True, "Подключение успешно"
        except Exception as exc:
            logger.error(f"[SSH] Connection failed: {exc}")
            return False, f"Ошибка подключения: {exc}"

    def _ensure_sftp(self) -> None:
        """Открыть SFTP по требованию (только для чтения)."""
        if self.sftp:
            return
        if not self.client:
            success, message = self.connect()
            if not success:
                raise Exception(f"SSH connection failed: {message}")
        try:
            self.sftp = self.client.open_sftp()
            logger.info(f"[SFTP] Opened SFTP session for {self.host}")
        except Exception as exc:
            raise Exception(f"SFTP not available: {exc}")

    def path_exists(self, path: str) -> bool:
        """Проверить существование пути через exec."""
        path_q = shlex.quote(path)
        try:
            output = self.execute(f"test -e {path_q} && echo 1 || echo 0")
            exists = output.strip() == "1"
            logger.info(f"[SSH] Path exists: {path} -> {exists}")
            return exists
        except Exception as e:
            logger.error(f"[SSH] Error checking path {path}: {e}")
            return False

    def list_directories(self, path: str) -> List[str]:
        """Получить список папок в указанном пути через exec."""
        path_q = shlex.quote(path)
        cmd = f"find {path_q} -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort"
        try:
            output = self.execute(cmd)
            directories = [line.strip() for line in output.split("\n") if line.strip()]
            logger.info(f"[SSH] Found {len(directories)} directories in {path}")
            return directories
        except Exception as e:
            logger.error(f"[SSH] Error listing {path}: {e}")
            return []

    def find_files(self, path: str, filename: str) -> List[str]:
        """Рекурсивно найти файлы с указанным именем через exec."""
        path_q = shlex.quote(path)
        exact_q = shlex.quote(filename)
        suffix_q = shlex.quote(f"*{filename}")
        cmd = (
            f"find {path_q} -type f \\("
            f" -name {exact_q} -o -name {suffix_q} \\) -print"
        )
        try:
            output = self.execute(cmd)
            found = [line.strip() for line in output.split("\n") if line.strip()]
            return found
        except Exception as e:
            logger.error(f"[SSH] Error finding files in {path}: {e}")
            return []

    def read_file(self, filepath: str) -> str:
        """Прочитать содержимое файла."""
        self._ensure_sftp()

        try:
            with self.sftp.file(filepath, "r") as f:
                content = f.read().decode("utf-8", errors="ignore")
            logger.info(f"[SFTP] Read file: {filepath} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"[SFTP] Error reading {filepath}: {e}")
            raise

    def write_file(self, filepath: str, content: str):
        """
        Записать содержимое в файл через exec.

        Стратегия:
        1. Собрать диагностику контекста
        2. Попробовать обычный tee
        3. Fallback на sudo tee если требуется
        """
        try:
            logger.info(
                f"[WRITE] Attempting to write to {filepath} ({len(content)} bytes)"
            )
            self.get_diagnostics(filepath)

            file_q = shlex.quote(filepath)
            cmd = f'sh -c "tee {file_q} > /dev/null"'
            _out, err, status = self._exec_command(
                cmd,
                get_pty=True,
                stdin_bytes=content.encode("utf-8"),
                log_output=False,
            )
            if status == 0:
                logger.info(f"[WRITE] Successfully wrote via tee")
                return

            logger.warning(f"[WRITE] tee failed: {err}")

            sudo_success = self.write_file_via_sudo_tee(filepath, content)
            if sudo_success:
                logger.info(f"[WRITE] Successfully wrote via sudo tee")
                return

            raise Exception(err or "tee failed")
        except Exception as e:
            error_msg = f"Error writing {filepath}: {e}"
            logger.error(f"[WRITE] {error_msg}")
            raise Exception(error_msg)

    def copy_file(self, src: str, dst: str):
        """Скопировать файл на сервере."""
        content = self.read_file(src)
        self.write_file(dst, content)
        logger.info(f"[SFTP] Copied {src} -> {dst}")

    def chmod(self, filepath: str, mode: int = 0o777):
        """Изменить права доступа к файлу.

        Args:
            filepath: Путь к файлу
            mode: Права доступа в восьмеричной системе (по умолчанию 0o777)
        """
        try:
            path_q = shlex.quote(filepath)
            self.execute(f"chmod {oct(mode)[2:]} {path_q}")
            logger.info(f"[SSH] Changed permissions for {filepath} to {oct(mode)}")
        except Exception as e:
            logger.error(f"[SSH] Error changing permissions for {filepath}: {e}")
            raise

    def get_file_owner(self, filepath: str) -> dict:
        """Получить информацию о владельце файла.

        Returns:
            Словарь с UID, GID и правами доступа
        """
        try:
            path_q = shlex.quote(filepath)
            output = self.execute(f"stat -c '%u %g %a %s' {path_q}")
            parts = [p for p in output.split() if p]
            if len(parts) < 4:
                raise Exception(f"Unexpected stat output: {output}")
            return {
                "uid": int(parts[0]),
                "gid": int(parts[1]),
                "mode": parts[2],
                "size": int(parts[3]),
            }
        except Exception as e:
            logger.error(f"[SSH] Error getting file owner for {filepath}: {e}")
            raise

    def _exec_command(
        self,
        command: str,
        get_pty: bool = False,
        stdin_bytes: bytes | None = None,
        log_output: bool = True,
    ) -> Tuple[str, str, int]:
        """
        Выполнить команду и вернуть stdout, stderr, exit code.

        Args:
            command: Bash команда
            get_pty: Запрашивать PTY
            stdin_bytes: Байты для STDIN

        Returns:
            (stdout_text, stderr_text, exit_status)
        """
        if not self.client:
            success, message = self.connect()
            if not success:
                raise Exception(f"SSH connection failed: {message}")

        logger.info(f"[SSH] Executing command: {command}")
        stdin, stdout, stderr = self.client.exec_command(command, get_pty=get_pty)

        if stdin_bytes is not None:
            stdin.write(stdin_bytes)
        try:
            stdin.close()
        except Exception:
            pass

        stdout_text = stdout.read().decode("utf-8", errors="ignore").strip()
        stderr_text = stderr.read().decode("utf-8", errors="ignore").strip()
        exit_status = stdout.channel.recv_exit_status()

        if log_output and stdout_text:
            logger.info(f"[SSH] STDOUT: {stdout_text}")
        if log_output and stderr_text:
            logger.warning(f"[SSH] STDERR: {stderr_text}")

        return stdout_text, stderr_text, exit_status

    def execute_raw(
        self,
        command: str,
        get_pty: bool = True,
        stdin_bytes: bytes | None = None,
        log_output: bool = True,
    ) -> Tuple[str, str, int]:
        """Выполнить команду и вернуть stdout/stderr/exit_code."""
        return self._exec_command(
            command, get_pty=get_pty, stdin_bytes=stdin_bytes, log_output=log_output
        )

    def execute(self, command: str, get_pty: bool = True) -> str:
        """
        Выполнить команду на сервере.

        Args:
            command: Bash команда

        Returns:
            Вывод команды

        Raises:
            Exception: Если подключение не установлено или ошибка выполнения
        """
        try:
            output, _error, _status = self._exec_command(command, get_pty=get_pty)
            # Возвращаем output даже если есть stderr (многие команды пишут в stderr)
            return output
        except Exception as e:
            logger.error(f"[SSH] Execute failed: {str(e)}")
            raise Exception(f"Execute failed: {str(e)}")

    def get_diagnostics(self, filepath: str) -> str:
        """
        Собрать диагностику контекста выполнения перед операциями.

        Returns:
            Строка с whoami, id, groups, pwd, umask, ls -l файла
        """
        try:
            path_q = shlex.quote(filepath)
            diag_cmd = f"whoami && id && groups && pwd && umask && ls -l {path_q} 2>&1"
            output = self.execute(diag_cmd, get_pty=True)
            logger.info(f"[DIAGNOSTICS] Context for {filepath}:\n{output}")
            return output
        except Exception as e:
            logger.error(f"[DIAGNOSTICS] Failed to get context: {e}")
            return ""

    def write_file_via_sudo_tee(self, filepath: str, content: str) -> bool:
        """
        Записать файл через 'sudo tee' (exec-канал, не SFTP).
        Используется для файлов, которые может писать только root.

        Args:
            filepath: Путь к файлу
            content: Содержимое для записи

        Returns:
            True если успешно, False если ошибка

        Raises:
            Exception: При критических ошибках подключения
        """
        if not self.client:
            success, message = self.connect()
            if not success:
                raise Exception(f"SSH connection failed: {message}")

        try:
            # Сначала получаем диагностику
            logger.info(f"[SUDO_TEE] Attempting to write via sudo tee: {filepath}")
            _ = self.get_diagnostics(filepath)

            # Проверить, может ли sudo работать без пароля
            _out, err, status = self._exec_command("sudo -n true")
            if status != 0:
                err_lower = err.lower()
                if "password" in err_lower or "a password" in err_lower:
                    logger.warning(
                        f"[SUDO_TEE] Sudo requires password (NOPASSWD needed): {err}"
                    )
                    return False
                if "requiretty" in err_lower or "a terminal is required" in err_lower:
                    logger.warning(f"[SUDO_TEE] Sudo requires TTY, will retry with PTY")
                else:
                    logger.warning(f"[SUDO_TEE] Sudo check failed: {err}")
                    return False

            # Выполняем запись через sudo tee
            file_q = shlex.quote(filepath)
            cmd = f'sh -c "sudo tee {file_q} > /dev/null"'
            logger.info(f"[SUDO_TEE] Executing: {cmd}")

            stdout_text, stderr_text, status = self._exec_command(
                cmd,
                get_pty=True,
                stdin_bytes=content.encode("utf-8"),
                log_output=False,
            )

            if status != 0:
                err_lower = stderr_text.lower()
                if "password" in err_lower:
                    logger.warning(
                        f"[SUDO_TEE] Sudo requires password (interactive mode needed): {stderr_text}"
                    )
                    return False
                logger.warning(f"[SUDO_TEE] Sudo tee failed: {stderr_text}")
                return False

            logger.info(
                f"[SUDO_TEE] Successfully wrote {len(content)} bytes to {filepath}"
            )
            return True

        except Exception as e:
            logger.error(f"[SUDO_TEE] Error writing via sudo tee: {e}")
            return False

    def close(self):
        """Закрыть подключение."""
        if self.sftp:
            self.sftp.close()
        if self.client:
            self.client.close()
        logger.info("[SSH] Connection closed")

    def __enter__(self):
        """Context manager."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager."""
        self.close()


def test_connection(
    host: str, port: int, username: str, password: str
) -> Tuple[bool, str]:
    """Тестирование подключения (существующая функция)."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=10,
            auth_timeout=10,
            banner_timeout=10,
        )
        stdin, stdout, stderr = client.exec_command("echo connected")
        _ = stdout.read()
        return True, "Подключение успешно"
    except Exception as exc:
        return False, f"Ошибка подключения: {exc}"
    finally:
        client.close()
