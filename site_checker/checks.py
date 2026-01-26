import asyncio
import secrets
import string
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from .config import CheckOptions, RuntimeOptions

USER_AGENT = "Mozilla/5.0 (compatible; LimeFrogChecker/1.0; +https://example.com)"

CSV_COLUMNS_BASE = [
    "URL",
    "Код ответа",
    "Редирект",
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
    "H1 пустой",
    "HTML структура",
    "Дубли H1/H2/H3",
]


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


def check_images_alt(soup: Optional[BeautifulSoup]) -> List[str]:
    if not soup or not soup.body:
        return []
    alts: List[str] = []
    for img in soup.body.find_all("img"):
        alt = img.get("alt")
        alts.append(alt.strip() if alt else "")
    return alts


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
        result = {col: "" for col in get_csv_columns(0)}
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

    # Собрать все значения
    alts = []
    if check_options.check_images:
        alts = check_images_alt(soup)

    # Определить максимальное количество альтов для создания колонок
    max_alts = len(alts)
    csv_columns = get_csv_columns(max_alts)

    # Создать результат с нужным количеством колонок
    result: Dict[str, str] = {col: "" for col in csv_columns}
    result["URL"] = normalized_url or raw_url

    if check_options.check_status_codes:
        result["Код ответа"] = str(response_no_follow.status_code)

    if check_options.check_redirects:
        if is_redirect:
            redirect_url = response_no_follow.headers.get("location", "")
            result["Редирект"] = redirect_url

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
        result["H1 пустой"] = h1_empty

    if check_options.check_images and alts:
        for idx, alt in enumerate(alts, start=1):
            result[f"Alt-{idx}"] = alt

    if check_options.check_html_structure:
        result["HTML структура"] = build_html_structure(soup, check_options)

    if check_options.check_heading_duplicates:
        result["Дубли H1/H2/H3"] = find_heading_duplicates(soup)

    return result
