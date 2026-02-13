import asyncio
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

from ..config import RuntimeOptions

# Импорт из корневого модуля (три уровня вверх)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from logging_config import mask_sensitive_url

logger = logging.getLogger("lime_frog")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


async def fetch_with_retries(
    client: httpx.AsyncClient,
    url: str,
    runtime: RuntimeOptions,
    follow_redirects: bool = True,
) -> Optional[httpx.Response]:
    """
    Выполняет HTTP запрос с повторными попытками при ошибках.

    Логирует все попытки, таймауты, DNS/SSL ошибки и финальный статус.
    """
    for attempt in range(runtime.retries + 1):
        start_time = time.time()
        try:
            response = await client.get(url, follow_redirects=follow_redirects)
            elapsed_ms = (time.time() - start_time) * 1000

            # Логируем успешный запрос
            logger.debug(
                f"HTTP {response.status_code} {mask_sensitive_url(url)} | {elapsed_ms:.0f}ms | "
                f"attempt {attempt + 1}/{runtime.retries + 1}"
            )

            return response

        except httpx.TimeoutException as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.warning(
                f"Timeout: {mask_sensitive_url(url)} | {elapsed_ms:.0f}ms | "
                f"attempt {attempt + 1}/{runtime.retries + 1}"
            )
            if attempt == runtime.retries:
                logger.error(f"Max retries reached for {mask_sensitive_url(url)} (timeout)")
                return None
            await asyncio.sleep(0.25)

        except httpx.ConnectError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_detail = str(e)[:100]
            logger.warning(
                f"Connection error: {mask_sensitive_url(url)} | {elapsed_ms:.0f}ms | {error_detail} | "
                f"attempt {attempt + 1}/{runtime.retries + 1}"
            )
            if attempt == runtime.retries:
                logger.error(f"Max retries reached for {mask_sensitive_url(url)} (connection)")
                return None
            await asyncio.sleep(0.25)

        except httpx.HTTPError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            error_type = type(e).__name__
            error_detail = str(e)[:100]
            logger.warning(
                f"{error_type}: {mask_sensitive_url(url)} | {elapsed_ms:.0f}ms | {error_detail} | "
                f"attempt {attempt + 1}/{runtime.retries + 1}"
            )
            if attempt == runtime.retries:
                logger.error(f"Max retries reached for {mask_sensitive_url(url)} ({error_type})")
                return None
            await asyncio.sleep(0.25)

    return None
