from typing import Dict, Optional, Tuple

from bs4 import BeautifulSoup

from ...context import CheckContext


def check_h1(ctx: CheckContext) -> Tuple[str, str]:
    """
    Проверяет H1 теги.
    Возвращает кортеж: (количество, пустой_ли)
    """
    soup = ctx.soup
    if not soup:
        return "нет данных", ""
    h1_tags = soup.find_all("h1")
    count = len(h1_tags)
    if count == 0:
        return "0", "нет"
    texts = [t.get_text(strip=True) for t in h1_tags]
    has_empty = any(not t for t in texts)
    return str(count), "да" if has_empty else "нет"


def collect_headings(ctx: CheckContext) -> Dict[str, str]:
    """
    Собирает содержимое заголовков H1-H6 в зависимости от настроек.
    Возвращает словарь с ключами H1-H6, значения - текст заголовков через =>
    """
    soup = ctx.soup
    result = {}
    heading_map = {
        "H1": ("h1", ctx.check_options.collect_h1),
        "H2": ("h2", ctx.check_options.collect_h2),
        "H3": ("h3", ctx.check_options.collect_h3),
        "H4": ("h4", ctx.check_options.collect_h4),
        "H5": ("h5", ctx.check_options.collect_h5),
        "H6": ("h6", ctx.check_options.collect_h6),
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


def find_heading_duplicates(ctx: CheckContext) -> str:
    soup = ctx.soup
    if not soup:
        return "нет данных"
    duplicates = []
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
