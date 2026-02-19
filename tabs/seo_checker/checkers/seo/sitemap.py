import httpx
from xml.etree import ElementTree as ET

from ...context import CheckContext
from ...network.fetcher import fetch_with_retries


async def check_sitemap(ctx: CheckContext) -> str:
    base_url = ctx.final_url if ctx.final_url else ctx.normalized_url
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    resp = await fetch_with_retries(ctx.client, sitemap_url, ctx.runtime)
    if not resp:
        return "нет ответа"
    return "200" if resp.status_code == 200 else str(resp.status_code)


async def get_pages_from_sitemap(ctx: CheckContext, max_pages: int = 100) -> str:
    """
    Извлекает страницы из sitemap.xml, включая вложенные sitemaps (sitemap index).

    Args:
        ctx: CheckContext с информацией о базовом URL
        max_pages: Максимальное количество страниц для сбора

    Returns:
        Строка с URL страниц, разделенными запятыми.
        Если sitemap не найден или пуст, возвращает пустую строку
    """

    async def fetch_pages_from_url(url: str) -> list:
        """Загружает и парсит один sitemap, извлекает страницы."""
        resp = await fetch_with_retries(ctx.client, url, ctx.runtime)
        if not resp or resp.status_code != 200:
            return []

        try:
            root = ET.fromstring(resp.text.encode("utf-8"))
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            pages = []

            # 1. Пробуем найти URL элементы (обычный sitemap)
            for url_elem in root.findall("ns:url", ns):
                loc = url_elem.find("ns:loc", ns)
                if loc is not None and loc.text:
                    pages.append(loc.text.strip())

            # Если с namespace не нашли, пробуем без namespace
            if not pages:
                for url_elem in root.findall("url"):
                    loc = url_elem.find("loc")
                    if loc is not None and loc.text:
                        pages.append(loc.text.strip())

            return pages

        except Exception:
            return []

    async def fetch_sitemaps_from_index(url: str) -> list:
        """Загружает sitemap index и возвращает список ссылок на другие sitemaps."""
        resp = await fetch_with_retries(ctx.client, url, ctx.runtime)
        if not resp or resp.status_code != 200:
            return []

        try:
            root = ET.fromstring(resp.text.encode("utf-8"))
            ns = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

            sitemaps = []

            # Ищем sitemap элементы (sitemap index)
            for sitemap_elem in root.findall("ns:sitemap", ns):
                loc = sitemap_elem.find("ns:loc", ns)
                if loc is not None and loc.text:
                    sitemaps.append(loc.text.strip())

            # Если с namespace не нашли, пробуем без namespace
            if not sitemaps:
                for sitemap_elem in root.findall("sitemap"):
                    loc = sitemap_elem.find("loc")
                    if loc is not None and loc.text:
                        sitemaps.append(loc.text.strip())

            return sitemaps

        except Exception:
            return []

    base_url = ctx.final_url if ctx.final_url else ctx.normalized_url
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"

    all_urls = []

    # Сначала проверяем, это sitemap index или обычный sitemap
    sitemaps_to_load = await fetch_sitemaps_from_index(sitemap_url)

    if sitemaps_to_load:
        # Это sitemap index, загружаем все вложенные sitemaps
        for sitemap_url_item in sitemaps_to_load:
            pages = await fetch_pages_from_url(sitemap_url_item)
            all_urls.extend(pages)
            if len(all_urls) >= max_pages:
                break
    else:
        # Это обычный sitemap, просто загружаем страницы
        all_urls = await fetch_pages_from_url(sitemap_url)

    # Ограничиваем количество страниц
    all_urls = all_urls[:max_pages]

    # Возвращаем URL через запятую
    return ", ".join(all_urls) if all_urls else ""
