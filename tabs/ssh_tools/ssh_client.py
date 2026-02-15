"""SSH клиент для тестового подключения."""

import logging
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
            # Открыть SFTP сессию
            self.sftp = self.client.open_sftp()
            logger.info(f"[SSH] Connected via SFTP to {self.host}")
            return True, "Подключение успешно"
        except Exception as exc:
            logger.error(f"[SSH] Connection failed: {exc}")
            return False, f"Ошибка подключения: {exc}"

    def path_exists(self, path: str) -> bool:
        """Проверить существование пути через SFTP."""
        if not self.sftp:
            success, _ = self.connect()
            if not success:
                return False

        try:
            self.sftp.stat(path)
            logger.info(f"[SFTP] Path exists: {path}")
            return True
        except FileNotFoundError:
            logger.warning(f"[SFTP] Path not found: {path}")
            return False
        except Exception as e:
            logger.error(f"[SFTP] Error checking path {path}: {e}")
            return False

    def list_directories(self, path: str) -> List[str]:
        """Получить список папок в указанном пути."""
        if not self.sftp:
            success, _ = self.connect()
            if not success:
                return []

        try:
            items = self.sftp.listdir_attr(path)
            directories = [
                item.filename
                for item in items
                if stat.S_ISDIR(item.st_mode)
            ]
            logger.info(f"[SFTP] Found {len(directories)} directories in {path}")
            return directories
        except Exception as e:
            logger.error(f"[SFTP] Error listing {path}: {e}")
            return []

    def find_files(self, path: str, filename: str) -> List[str]:
        """Рекурсивно найти файлы с указанным именем."""
        if not self.sftp:
            success, _ = self.connect()
            if not success:
                return []

        found = []
        try:
            # Проверить текущую директорию
            try:
                items = self.sftp.listdir_attr(path)
            except:
                return []

            for item in items:
                item_path = f"{path}/{item.filename}"

                if stat.S_ISDIR(item.st_mode):
                    # Рекурсия в поддиректории
                    found.extend(self.find_files(item_path, filename))
                elif item.filename == filename or item.filename.endswith(filename):
                    found.append(item_path)

            return found
        except Exception as e:
            logger.error(f"[SFTP] Error finding files in {path}: {e}")
            return found

    def read_file(self, filepath: str) -> str:
        """Прочитать содержимое файла."""
        if not self.sftp:
            success, _ = self.connect()
            if not success:
                raise Exception("SFTP not connected")

        try:
            with self.sftp.file(filepath, 'r') as f:
                content = f.read().decode('utf-8', errors='ignore')
            logger.info(f"[SFTP] Read file: {filepath} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"[SFTP] Error reading {filepath}: {e}")
            raise

    def write_file(self, filepath: str, content: str):
        """Записать содержимое в файл."""
        if not self.sftp:
            success, _ = self.connect()
            if not success:
                raise Exception("SFTP not connected")

        try:
            with self.sftp.file(filepath, 'w') as f:
                f.write(content.encode('utf-8'))
            logger.info(f"[SFTP] Wrote file: {filepath} ({len(content)} bytes)")
        except Exception as e:
            logger.error(f"[SFTP] Error writing {filepath}: {e}")
            raise

    def copy_file(self, src: str, dst: str):
        """Скопировать файл на сервере."""
        content = self.read_file(src)
        self.write_file(dst, content)
        logger.info(f"[SFTP] Copied {src} -> {dst}")

    def execute(self, command: str) -> str:
        """
        Выполнить команду на сервере.

        Args:
            command: Bash команда

        Returns:
            Вывод команды

        Raises:
            Exception: Если подключение не установлено или ошибка выполнения
        """
        if not self.client:
            success, message = self.connect()
            if not success:
                raise Exception(f"SSH connection failed: {message}")

        try:
            logger.info(f"[SSH] Executing command: {command}")
            stdin, stdout, stderr = self.client.exec_command(command)
            output = stdout.read().decode('utf-8', errors='ignore').strip()
            error = stderr.read().decode('utf-8', errors='ignore').strip()

            logger.info(f"[SSH] STDOUT: {output}")
            if error:
                logger.warning(f"[SSH] STDERR: {error}")

            # Возвращаем output даже если есть stderr (многие команды пишут в stderr)
            return output
        except Exception as e:
            logger.error(f"[SSH] Execute failed: {str(e)}")
            raise Exception(f"Execute failed: {str(e)}")

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


def test_connection(host: str, port: int, username: str, password: str) -> Tuple[bool, str]:
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
