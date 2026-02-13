import secrets
from typing import Tuple

import httpx

from ...context import CheckContext
from ...network.fetcher import fetch_with_retries


async def check_404(ctx: CheckContext) -> Tuple[str, str, str]:
    """
    Проверяет страницу 404.
    Возвращает кортеж: (URL, код_ответа, корректность)
    """
    base_url = ctx.final_url if ctx.final_url else ctx.normalized_url
    token = secrets.token_hex(5)
    test_url = base_url.rstrip("/") + f"/{token}"
    resp = await fetch_with_retries(ctx.client, test_url, ctx.runtime)
    if not resp:
        return "нет ответа", "", ""
    is_correct = "да" if resp.status_code == 404 else "нет"
    return test_url, str(resp.status_code), is_correct
