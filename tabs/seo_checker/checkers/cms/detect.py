import asyncio
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from ...context import CheckContext
from ...network.fetcher import fetch_with_retries


async def check_cms(ctx: CheckContext) -> str:
    """Определяет используемую CMS (фокус на WordPress)."""
    response = ctx.response
    if not response:
        return "Unknown"

    response_text = response.text or ""
    response_lower = response_text.lower()
    soup = ctx.soup

    features = set()

    # Базовые текстовые индикаторы в HTML
    if "wp-content" in response_lower:
        features.add("wp-content")
    if "wp-includes" in response_lower:
        features.add("wp-includes")
    if "wp-json" in response_lower or "/wp/v2/" in response_lower:
        features.add("wp-json")
    if "wp-embed.min.js" in response_lower or "wp-emoji-release.min.js" in response_lower:
        features.add("wp-scripts")

    # meta generator
    if soup:
        meta_generator = soup.find("meta", attrs={"name": "generator"})
        if meta_generator:
            content = meta_generator.get("content", "")
            if content and "wordpress" in content.lower():
                features.add("meta_generator")

    # Link заголовок с wp-json
    link_header = response.headers.get("link", "").lower()
    if "wp-json" in link_header or "api.w.org" in link_header:
        features.add("header_link")

    # Cookies с префиксом wordpress_
    if any((name or "").lower().startswith("wordpress_") for name in response.cookies):
        features.add("wp_cookies")

    # Поиск хотя бы одной ссылки с wp-признаками (фикс бага накручивания hits)
    if soup:
        has_wp_link = False
        for tag in soup.find_all(["a", "link", "script", "img"]):
            href = (tag.get("href") or tag.get("src") or "").lower()
            if not href:
                continue
            if any(marker in href for marker in [
                "wp-content", "wp-includes", "wp-admin", "wp-login.php", "wp-json"
            ]):
                has_wp_link = True
                break

        if has_wp_link:
            features.add("wp_links")

    # Если уже достаточно признаков
    if len(features) >= 2:
        return "WordPress"

    # Дополнительные сетевые проверки
    parsed = urlparse(str(response.url))
    base_root = (
        f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    )

    if base_root:
        async def check_endpoint(url: str) -> bool:
            if not url:
                return False
            try:
                resp = await fetch_with_retries(ctx.client, url, ctx.runtime, follow_redirects=False)
                return bool(resp and resp.status_code in (200, 302))
            except Exception:
                return False

        login_ok, admin_ok, rest_ok = await asyncio.gather(
            check_endpoint(base_root + "/wp-login.php"),
            check_endpoint(base_root + "/wp-admin/"),
            check_endpoint(base_root + "/wp-json/"),
        )

        if login_ok:
            features.add("endpoint_login")
        if admin_ok:
            features.add("endpoint_admin")
        if rest_ok:
            features.add("endpoint_rest")

    if len(features) >= 2:
        return "WordPress"

    # Проверка Forge
    forge_indicators = [
        "encrypted.php?key=btn_link1",
        "./styles/tinymce.css",
        "application/ld+json",
    ]

    for indicator in forge_indicators:
        if indicator in response_text:
            return "Forge"

    return "Unknown"
