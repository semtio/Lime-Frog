import asyncio
import secrets
import string
from typing import Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from .config import CheckOptions, RuntimeOptions
from .context import CheckContext
from .network.fetcher import fetch_with_retries, BROWSER_HEADERS
from .network.url import normalize_url
from .parsers.meta import extract_title, extract_description, extract_html_lang, extract_canonical, parse_robots_meta
from .checkers.seo.sitemap import check_sitemap
from .checkers.seo.robots import check_robots
from .checkers.seo.http import check_404
from .checkers.seo.headings import check_h1, collect_headings, find_heading_duplicates
from .checkers.seo.images import check_images_alt
from .checkers.seo.structure import build_html_structure
from .checkers.cms.detect import check_cms

CSV_COLUMNS_BASE = [
    "URL",
    "Код ответа",
    "Редирект",
    "Язык сайта",
    "Noindex",
    "Nofollow",
    "Canonical",
    "Title",
    "Title Длина",
    "Description",
    "Description Длина",
    "Sitemap 200",
    "Robots 200",
    "Robots Disallow",
    "Robots Sitemap",
    "Ссылка на стр.404",
    "Код стр.404",
    "Корректность 404",
    "Кол-во H1",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "HTML структура",
    "Дубли H1/H2/H3",
    "Кол-во img",
    "Кол-во alt",
    "CMS",
]


def get_active_columns(check_options: CheckOptions, max_alts: int = 0) -> List[str]:
    """Возвращает список активных колонок на основе включенных опций."""
    cols = ["URL"]  # URL всегда присутствует

    if check_options.check_status_codes:
        cols.append("Код ответа")

    if check_options.check_redirects:
        cols.append("Редирект")

    if check_options.check_html_lang:
        cols.append("Язык сайта")

    if check_options.check_indexability:
        cols.extend(["Noindex", "Nofollow", "Canonical"])

    if check_options.check_titles:
        cols.extend(["Title", "Title Длина", "Description", "Description Длина"])

    if check_options.check_sitemap:
        cols.append("Sitemap 200")

    if check_options.check_robots:
        cols.extend(["Robots 200", "Robots Disallow", "Robots Sitemap"])

    if check_options.check_404:
        cols.extend(["Ссылка на стр.404", "Код стр.404", "Корректность 404"])

    if check_options.check_h1:
        cols.append("Кол-во H1")

    # Заголовки H1-H6
    if check_options.collect_h1:
        cols.append("H1")
    if check_options.collect_h2:
        cols.append("H2")
    if check_options.collect_h3:
        cols.append("H3")
    if check_options.collect_h4:
        cols.append("H4")
    if check_options.collect_h5:
        cols.append("H5")
    if check_options.collect_h6:
        cols.append("H6")

    if check_options.check_html_structure:
        cols.append("HTML структура")

    if check_options.check_heading_duplicates:
        cols.append("Дубли H1/H2/H3")

    if check_options.check_images:
        cols.extend(["Кол-во img", "Кол-во alt"])
        # Alt колонки добавляются динамически
        for i in range(1, max_alts + 1):
            cols.append(f"Alt-{i}")

    if check_options.check_cms:
        cols.append("CMS")

    return cols


def get_csv_columns(max_alts: int = 0) -> List[str]:
    cols = CSV_COLUMNS_BASE.copy()
    for i in range(1, max_alts + 1):
        cols.append(f"Alt-{i}")
    return cols


async def run_all_checks(
    raw_url: str,
    client: httpx.AsyncClient,
    check_options: CheckOptions,
    runtime: RuntimeOptions,
) -> Dict[str, str]:
    normalized_url = normalize_url(raw_url)

    if not normalized_url:
        return {"URL": raw_url, "Код ответа": "некорректный адрес"}

    # Получить первоначальный ответ (без следования редиректам)
    response_no_follow = await fetch_with_retries(
        client, normalized_url, runtime, follow_redirects=False
    )
    if not response_no_follow:
        return {"URL": normalized_url or raw_url, "Код ответа": "нет ответа"}

    # Проверяем, есть ли редирект
    is_redirect = response_no_follow.status_code in (301, 302, 303, 307, 308)

    # Если редирект и НЕ следуем редиректам - возвращаем только базовую информацию
    if is_redirect and not check_options.follow_redirects_for_checks:
        redirect_url = response_no_follow.headers.get("location", "")
        result = {col: "" for col in get_active_columns(check_options, 0)}
        result["URL"] = normalized_url or raw_url
        if check_options.check_status_codes:
            result["Код ответа"] = str(response_no_follow.status_code)
        if check_options.check_redirects:
            result["Редирект"] = redirect_url
        return result

    # Получить финальный ответ (после всех редиректов) для контента
    response = await fetch_with_retries(client, normalized_url, runtime)
    if not response:
        response = response_no_follow

    soup = None
    if "text/html" in response.headers.get("content-type", ""):
        soup = BeautifulSoup(response.text, "lxml")

    # Определить финальный URL для использования в проверках
    final_url = (
        str(response.url)
        if is_redirect and check_options.follow_redirects_for_checks
        else normalized_url
    )

    # Создать контекст проверки
    ctx = CheckContext(
        raw_url=raw_url,
        normalized_url=normalized_url,
        response_no_follow=response_no_follow,
        response=response,
        soup=soup,
        client=client,
        check_options=check_options,
        runtime=runtime,
        final_url=final_url,
        is_redirect=is_redirect,
    )

    # Собрать все значения
    alts = []
    img_count = "0"
    alt_count = "0"
    if check_options.check_images:
        alts, img_count, alt_count = check_images_alt(ctx)

    # Определить максимальное количество альтов для создания колонок
    max_alts = len(alts)
    csv_columns = get_active_columns(check_options, max_alts)

    # Создать результат с нужным количеством колонок
    result: Dict[str, str] = {col: "" for col in csv_columns}
    result["URL"] = normalized_url or raw_url

    if check_options.check_status_codes:
        result["Код ответа"] = str(response_no_follow.status_code)

    if check_options.check_redirects:
        if is_redirect:
            redirect_url = response_no_follow.headers.get("location", "")
            result["Редирект"] = redirect_url

    if check_options.check_html_lang:
        result["Язык сайта"] = extract_html_lang(soup)

    if check_options.check_indexability:
        noindex, nofollow = parse_robots_meta(response, soup)
        result["Noindex"] = "да" if noindex else "нет"
        result["Nofollow"] = "да" if nofollow else "нет"
        result["Canonical"] = extract_canonical(soup) if soup else ""

    if check_options.check_titles:
        title, t_len = extract_title(soup)
        result["Title"] = title
        result["Title Длина"] = str(t_len) if t_len > 0 else ""
        desc, d_len = extract_description(soup)
        result["Description"] = desc
        result["Description Длина"] = str(d_len) if d_len > 0 else ""

    # Выполнить проверки с передачей контекста
    if check_options.check_sitemap:
        result["Sitemap 200"] = await check_sitemap(ctx)

    if check_options.check_robots:
        robots_result = await check_robots(ctx)
        result.update(robots_result)

    if check_options.check_404:
        page_404_url, page_404_code, page_404_correct = await check_404(ctx)
        result["Ссылка на стр.404"] = page_404_url
        result["Код стр.404"] = page_404_code
        result["Корректность 404"] = page_404_correct

    if check_options.check_h1:
        h1_count, h1_empty = check_h1(ctx)
        result["Кол-во H1"] = h1_count

    # Сбор содержимого заголовков H1-H6
    headings = collect_headings(ctx)
    for heading_key, heading_text in headings.items():
        result[heading_key] = heading_text

    if check_options.check_html_structure:
        result["HTML структура"] = build_html_structure(ctx)

    if check_options.check_heading_duplicates:
        result["Дубли H1/H2/H3"] = find_heading_duplicates(ctx)

    if check_options.check_images:
        result["Кол-во img"] = img_count
        result["Кол-во alt"] = alt_count
        if alts:
            for idx, alt in enumerate(alts, start=1):
                result[f"Alt-{idx}"] = alt

    # Проверка CMS
    if check_options.check_cms:
        result["CMS"] = await check_cms(ctx)

    return result
