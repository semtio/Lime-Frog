import asyncio
import re
import secrets
import string
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from .config import CheckOptions, RuntimeOptions

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

BROWSER_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

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
    "CMS Debug",
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
        cols.extend(["CMS", "CMS Debug"])

    return cols


def get_csv_columns(max_alts: int = 0) -> List[str]:
    cols = CSV_COLUMNS_BASE.copy()
    for i in range(1, max_alts + 1):
        cols.append(f"Alt-{i}")
    return cols


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path or "/")
    return urlunparse(normalized)


async def fetch_with_retries(
    client: httpx.AsyncClient,
    url: str,
    runtime: RuntimeOptions,
    follow_redirects: bool = True,
) -> Optional[httpx.Response]:
    for attempt in range(runtime.retries + 1):
        try:
            return await client.get(url, follow_redirects=follow_redirects)
        except httpx.HTTPError:
            if attempt == runtime.retries:
                return None
            await asyncio.sleep(0.25)
    return None


def parse_robots_meta(
    response: httpx.Response, soup: Optional[BeautifulSoup]
) -> Tuple[bool, bool]:
    header = response.headers.get("x-robots-tag", "").lower()
    noindex = "noindex" in header
    nofollow = "nofollow" in header
    if soup:
        for tag in soup.find_all("meta", attrs={"name": "robots"}):
            content = (tag.get("content") or "").lower()
            noindex = noindex or "noindex" in content
            nofollow = nofollow or "nofollow" in content
    return noindex, nofollow


def extract_canonical(soup: Optional[BeautifulSoup]) -> str:
    if not soup:
        return ""
    tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    return (tag.get("href") or "").strip() if tag else ""


def extract_html_lang(soup: Optional[BeautifulSoup]) -> str:
    """Извлекает значение атрибута lang из тега <html>"""
    if not soup:
        return ""
    html_tag = soup.find("html")
    if html_tag and html_tag.has_attr("lang"):
        return html_tag["lang"].strip()
    return ""


def extract_title(soup: Optional[BeautifulSoup]) -> Tuple[str, int]:
    if not soup or not soup.title or not soup.title.string:
        return "", 0
    text = soup.title.string.strip()
    return text, len(text)


def extract_description(soup: Optional[BeautifulSoup]) -> Tuple[str, int]:
    if not soup:
        return "", 0
    tag = soup.find("meta", attrs={"name": "description"})
    content = (tag.get("content") or "").strip() if tag else ""
    return content, len(content)


async def check_sitemap(
    base_url: str, client: httpx.AsyncClient, runtime: RuntimeOptions
) -> str:
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    resp = await fetch_with_retries(client, sitemap_url, runtime)
    if not resp:
        return "нет ответа"
    return "200" if resp.status_code == 200 else str(resp.status_code)


async def check_robots(
    base_url: str, client: httpx.AsyncClient, runtime: RuntimeOptions
) -> Dict[str, str]:
    robots_url = base_url.rstrip("/") + "/robots.txt"
    resp = await fetch_with_retries(client, robots_url, runtime)
    result = {"Robots 200": "", "Robots Disallow": "", "Robots Sitemap": ""}
    if not resp:
        return result
    result["Robots 200"] = "200" if resp.status_code == 200 else str(resp.status_code)
    if resp.status_code == 200:
        body = resp.text.lower()
        # Собираем все Disallow директивы
        disallows = []
        for line in resp.text.split("\n"):
            line_lower = line.lower().strip()
            if line_lower.startswith("disallow:"):
                path = line[9:].strip()  # Берем после "disallow:"
                if path:
                    disallows.append(path)
        result["Robots Disallow"] = " | ".join(disallows) if disallows else ""
        result["Robots Sitemap"] = "да" if "sitemap: " in body else "нет"
    return result


async def check_404(
    base_url: str, client: httpx.AsyncClient, runtime: RuntimeOptions
) -> Tuple[str, str, str]:
    """
    Проверяет страницу 404.
    Возвращает кортеж: (URL, код_ответа, корректность)
    """
    token = secrets.token_hex(5)
    test_url = base_url.rstrip("/") + f"/{token}"
    resp = await fetch_with_retries(client, test_url, runtime)
    if not resp:
        return "нет ответа", "", ""
    is_correct = "да" if resp.status_code == 404 else "нет"
    return test_url, str(resp.status_code), is_correct


def check_h1(soup: Optional[BeautifulSoup]) -> Tuple[str, str]:
    """
    Проверяет H1 теги.
    Возвращает кортеж: (количество, пустой_ли)
    """
    if not soup:
        return "нет данных", ""
    h1_tags = soup.find_all("h1")
    count = len(h1_tags)
    if count == 0:
        return "0", "нет"
    texts = [t.get_text(strip=True) for t in h1_tags]
    has_empty = any(not t for t in texts)
    return str(count), "да" if has_empty else "нет"


def collect_headings(
    soup: Optional[BeautifulSoup], check_options: CheckOptions
) -> Dict[str, str]:
    """
    Собирает содержимое заголовков H1-H6 в зависимости от настроек.
    Возвращает словарь с ключами H1-H6, значения - текст заголовков через =>
    """
    result = {}
    heading_map = {
        "H1": ("h1", check_options.collect_h1),
        "H2": ("h2", check_options.collect_h2),
        "H3": ("h3", check_options.collect_h3),
        "H4": ("h4", check_options.collect_h4),
        "H5": ("h5", check_options.collect_h5),
        "H6": ("h6", check_options.collect_h6),
    }

    if not soup:
        for key in heading_map.keys():
            result[key] = ""
        return result

    for key, (tag, enabled) in heading_map.items():
        if not enabled:
            result[key] = ""
            continue

        tags = soup.find_all(tag)
        if not tags:
            result[key] = ""
        else:
            texts = [t.get_text(strip=True) for t in tags if t.get_text(strip=True)]
            result[key] = " => ".join(texts) if texts else ""

    return result


def check_images_alt(soup: Optional[BeautifulSoup]) -> Tuple[List[str], str, str]:
    """
    Проверяет изображения и их alt атрибуты в body.
    Возвращает кортеж: (список_alt, кол_во_img, кол_во_alt)
    """
    if not soup or not soup.body:
        return [], "0", "0"

    alts: List[str] = []
    total_img = 0
    filled_alt = 0

    for img in soup.body.find_all("img"):
        total_img += 1
        alt = img.get("alt")
        alt_text = alt.strip() if alt else ""
        alts.append(alt_text)
        if alt_text:  # Считаем только заполненные alt
            filled_alt += 1

    return alts, str(total_img), str(filled_alt)


def build_html_structure(
    soup: Optional[BeautifulSoup], options: Optional["CheckOptions"] = None
) -> str:
    if not soup:
        return "нет данных"

    # Определяем какие теги отслеживать на основе настроек
    tags_to_track = []

    if options is None or options.html_track_headings:
        tags_to_track.extend(["h1", "h2", "h3", "h4", "h5", "h6"])

    if options is None or options.html_track_paragraphs:
        tags_to_track.append("p")

    if options is None or options.html_track_semantic:
        tags_to_track.extend(
            ["main", "section", "article", "header", "footer", "nav", "aside"]
        )

    if options and options.html_track_media:
        tags_to_track.extend(["figure", "figcaption"])

    if options and options.html_track_other:
        tags_to_track.extend(["address", "time"])

    if not tags_to_track:
        return "нет выбранных тегов"

    sequence: List[str] = []
    for tag in soup.find_all(tags_to_track):
        sequence.append(tag.name.upper())
    return ">".join(sequence) if sequence else "нет структурных элементов"


def find_heading_duplicates(soup: Optional[BeautifulSoup]) -> str:
    if not soup:
        return "нет данных"
    duplicates: List[str] = []
    for name in ["h1", "h2", "h3"]:
        texts: Dict[str, int] = {}
        for tag in soup.find_all(name):
            text = tag.get_text(strip=True).lower()
            if not text:
                continue
            texts[text] = texts.get(text, 0) + 1
        dup_items = [t for t, count in texts.items() if count > 1]
        if dup_items:
            duplicates.append(f"{name.upper()}: {', '.join(dup_items)}")
    return " | ".join(duplicates) if duplicates else "дубликатов нет"


async def check_cms(
    url: str,
    client: httpx.AsyncClient,
    runtime: RuntimeOptions,
) -> Tuple[str, str]:
    """Определяет CMS (фокус на WordPress) с диагностикой.

    Возвращает: (cms_name, debug_reason)
    """
    features = set()
    debug_log = []

    # 1. Попытка HTTPS с браузерными заголовками
    try:
        response = await client.get(url, follow_redirects=True, headers=BROWSER_HEADERS)
        status_initial = response.status_code
        final_url = str(response.url)
        debug_log.append(f"https_ok | status={status_initial} | final={final_url}")
    except httpx.ConnectError as e:
        debug_log.append(f"https_connect_error: {str(e)[:100]}")
        # Fallback на HTTP
        http_url = url.replace("https://", "http://")
        try:
            response = await client.get(
                http_url, follow_redirects=True, headers=BROWSER_HEADERS
            )
            status_initial = response.status_code
            final_url = str(response.url)
            debug_log.append(
                f"http_fallback_ok | status={status_initial} | final={final_url}"
            )
        except Exception as fallback_e:
            return "Unknown", f"connection_failed: {str(fallback_e)[:100]}"
    except httpx.TimeoutException:
        return "Unknown", "timeout"
    except Exception as e:
        return "Unknown", f"request_error: {str(e)[:100]}"

    # 2. Проверка статуса
    if status_initial >= 400:
        return "Unknown", f"http_{status_initial}"

    # 3. Проверка content-type
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return "Unknown", f"non_html_content_type: {content_type}"

    # 4. Проверка длины HTML
    response_text = response.text or ""
    html_len = len(response_text)
    debug_log.append(f"html_len={html_len}")

    if html_len < 500:
        return "Unknown", f"short_html: {html_len}b"

    response_lower = response_text.lower()

    # 5. Быстрые текстовые признаки WordPress
    if "wp-content" in response_lower:
        features.add("wp-content")
    if "wp-includes" in response_lower:
        features.add("wp-includes")
    if "wp-json" in response_lower or "/wp/v2/" in response_lower:
        features.add("wp-json")
    if "xmlrpc.php" in response_lower:
        features.add("xmlrpc")
    if (
        "wp-embed.min.js" in response_lower
        or "wp-emoji-release.min.js" in response_lower
    ):
        features.add("wp-scripts")

    # 6. Парсинг BeautifulSoup
    try:
        soup = BeautifulSoup(response_text, "lxml")
    except Exception:
        soup = None

    if soup:
        # meta generator
        meta_gen = soup.find("meta", attrs={"name": "generator"})
        if meta_gen:
            content = (meta_gen.get("content") or "").lower()
            if "wordpress" in content:
                features.add("meta_generator")

        # link rel="https://api.w.org/"
        for link_tag in soup.find_all("link"):
            href = (link_tag.get("href") or "").lower()
            if "api.w.org" in href or "wp-json" in href:
                features.add("link_api_w_org")
                break

        # Проверка наличия хотя бы одной ссылки с wp-признаками
        has_wp_link = False
        for tag in soup.find_all(["a", "link", "script", "img"]):
            href = (tag.get("href") or tag.get("src") or "").lower()
            if not href:
                continue
            if any(
                marker in href
                for marker in [
                    "wp-content",
                    "wp-includes",
                    "wp-admin",
                    "wp-login.php",
                    "xmlrpc.php",
                ]
            ):
                has_wp_link = True
                break

        if has_wp_link:
            features.add("wp_links")

    # 7. HTTP заголовки
    link_header = response.headers.get("link", "").lower()
    if "wp-json" in link_header or "api.w.org" in link_header:
        features.add("header_link_wp")

    # Cookies wordpress_*
    if any((name or "").lower().startswith("wordpress_") for name in response.cookies):
        features.add("wp_cookies")

    debug_log.append(f"features={len(features)}: {', '.join(sorted(features))}")

    # 8. Решение по WordPress
    if len(features) >= 2:
        return "WordPress", " | ".join(debug_log)

    # 9. Опциональные сетевые проверки (только если быстрых признаков < 2)
    parsed = urlparse(final_url)
    base_root = (
        f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
    )

    if base_root:
        network_features = set()
        short_timeout = httpx.Timeout(5.0)  # короткий таймаут

        async def check_endpoint(endpoint: str) -> bool:
            try:
                resp = await client.get(
                    base_root + endpoint,
                    follow_redirects=False,
                    headers=BROWSER_HEADERS,
                    timeout=short_timeout,
                )
                return resp.status_code in (200, 302, 403)
            except Exception:
                return False

        checks = await asyncio.gather(
            check_endpoint("/wp-login.php"),
            check_endpoint("/wp-admin/"),
            check_endpoint("/wp-json/"),
            return_exceptions=True,
        )

        if checks[0]:
            network_features.add("endpoint_wp_login")
        if checks[1]:
            network_features.add("endpoint_wp_admin")
        if checks[2]:
            network_features.add("endpoint_wp_json")

        features.update(network_features)
        debug_log.append(
            f"network_features={len(network_features)}: {', '.join(sorted(network_features))}"
        )

    if len(features) >= 2:
        return "WordPress", " | ".join(debug_log)

    # 10. Проверка Forge
    forge_indicators = [
        "encrypted.php?key=btn_link1",
        "./styles/tinymce.css",
    ]

    for indicator in forge_indicators:
        if indicator in response_text:
            return "Forge", " | ".join(debug_log)

    # Не определено
    reason = (
        "no_wp_signals"
        if len(features) == 0
        else f"insufficient_signals: {len(features)}"
    )
    return "Unknown", f"{reason} | " + " | ".join(debug_log)


async def check_domain_redirects(
    final_url: str, client: httpx.AsyncClient, runtime: RuntimeOptions
) -> str:
    parsed = urlparse(final_url)
    domain = parsed.netloc
    base_path = parsed.path if parsed.path else "/"
    targets = {
        f"http://{domain}{base_path}",
        f"https://{domain}{base_path}",
        f"http://www.{domain}{base_path}",
        f"https://www.{domain}{base_path}",
    }
    canonical = final_url
    reports: List[str] = []
    for candidate in sorted(targets):
        resp = await fetch_with_retries(client, candidate, runtime)
        if not resp:
            reports.append(f"{candidate} -> нет ответа")
            continue
        reports.append(f"{candidate} -> {resp.url} ({resp.status_code})")
    return " | ".join(reports)


async def run_all_checks(
    raw_url: str,
    client: httpx.AsyncClient,
    check_options: CheckOptions,
    runtime: RuntimeOptions,
) -> Dict[str, str]:
    normalized_url = normalize_url(raw_url)

    if not normalized_url:
        columns = get_active_columns(check_options, 0)
        result: Dict[str, str] = {col: "" for col in columns}
        result["URL"] = raw_url
        if check_options.check_status_codes:
            result["Код ответа"] = "некорректный адрес"
        if check_options.check_cms:
            result["CMS"] = "Unknown"
            result["CMS Debug"] = "invalid_url"
        return result

    # Получить первоначальный ответ (без следования редиректам)
    response_no_follow = await fetch_with_retries(
        client, normalized_url, runtime, follow_redirects=False
    )
    if not response_no_follow:
        columns = get_active_columns(check_options, 0)
        result: Dict[str, str] = {col: "" for col in columns}
        result["URL"] = normalized_url or raw_url
        if check_options.check_status_codes:
            result["Код ответа"] = "нет ответа"
        if check_options.check_cms:
            result["CMS"] = "Unknown"
            result["CMS Debug"] = "no_response_initial"
        return result

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
        if check_options.check_cms:
            result["CMS"] = "Unknown"
            result["CMS Debug"] = "redirect_not_followed"
        return result

    # Получить финальный ответ (после всех редиректов) для контента
    response = await fetch_with_retries(client, normalized_url, runtime)
    if not response:
        response = response_no_follow

    soup = None
    if "text/html" in response.headers.get("content-type", ""):
        soup = BeautifulSoup(response.text, "lxml")

    # Собрать все значения
    alts = []
    img_count = "0"
    alt_count = "0"
    if check_options.check_images:
        alts, img_count, alt_count = check_images_alt(soup)

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

    # Для проверок sitemap/robots/404 используем конечный URL (после редиректа)
    check_url = (
        str(response.url)
        if is_redirect and check_options.follow_redirects_for_checks
        else normalized_url
    )

    if check_options.check_sitemap:
        result["Sitemap 200"] = await check_sitemap(check_url, client, runtime)

    if check_options.check_robots:
        robots_result = await check_robots(check_url, client, runtime)
        result.update(robots_result)

    if check_options.check_404:
        page_404_url, page_404_code, page_404_correct = await check_404(
            check_url, client, runtime
        )
        result["Ссылка на стр.404"] = page_404_url
        result["Код стр.404"] = page_404_code
        result["Корректность 404"] = page_404_correct

    if check_options.check_h1:
        h1_count, h1_empty = check_h1(soup)
        result["Кол-во H1"] = h1_count

    # Сбор содержимого заголовков H1-H6
    headings = collect_headings(soup, check_options)
    for heading_key, heading_text in headings.items():
        result[heading_key] = heading_text

    if check_options.check_html_structure:
        result["HTML структура"] = build_html_structure(soup, check_options)

    if check_options.check_heading_duplicates:
        result["Дубли H1/H2/H3"] = find_heading_duplicates(soup)

    if check_options.check_images:
        result["Кол-во img"] = img_count
        result["Кол-во alt"] = alt_count
        if alts:
            for idx, alt in enumerate(alts, start=1):
                result[f"Alt-{idx}"] = alt

    # Проверка CMS (независимый запрос)
    if check_options.check_cms:
        cms_value, cms_debug = await check_cms(normalized_url, client, runtime)
        result["CMS"] = cms_value
        result["CMS Debug"] = cms_debug

    return result
