from typing import List, Optional, Tuple

from bs4 import BeautifulSoup

from ...context import CheckContext


def check_images_alt(ctx: CheckContext) -> Tuple[List[str], str, str]:
    """
    Проверяет изображения и их alt атрибуты в body.
    Возвращает кортеж: (список_alt, кол_во_img, кол_во_alt)
    """
    soup = ctx.soup
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


# JPG/JPEG and TIF/TIFF share a column pair. Unknown extensions are retained.
IMAGE_FORMATS = ("JPEG", "PNG", "GIF", "WebP", "AVIF", "SVG", "BMP", "TIFF", "ICO", "Другие")
IMAGE_FORMAT_COLUMNS = [
    column
    for image_format in IMAGE_FORMATS
    for column in (f"{image_format}: количество", f"{image_format}: ссылки на изображения")
]


def collect_image_formats(ctx: CheckContext) -> dict:
    """Collect unique HTTP image URLs per format without downloading images.

    Includes img sources and picture alternatives, not CSS backgrounds.
    Counts match the comma-separated URL lists; repeated URLs count once.
    """
    import re
    from urllib.parse import unquote, urljoin, urlsplit

    grouped = {name: {} for name in IMAGE_FORMATS}
    soup = ctx.soup
    if soup is not None:
        base_url = str(ctx.response.url) if ctx.response is not None else (ctx.final_url or ctx.normalized_url)
        base = soup.find("base", href=True)
        if base:
            base_url = urljoin(base_url, base["href"])
        for tag in soup.select("img, picture source"):
            candidates = []
            for attr in ("src", "data-src", "data-original", "data-lazy-src"):
                if tag.get(attr):
                    candidates.append(tag[attr].strip())
            for attr in ("srcset", "data-srcset", "data-lazy-srcset"):
                # A URL can contain commas (notably data URLs). Descriptors
                # are separated by whitespace, so do not simply split(',').
                srcset = tag.get(attr, "")
                candidates.extend(
                    match.group(1).rstrip(",")
                    for match in re.finditer(r"(?:^|\s|,\s*)([^\s]+)(?:\s+[^,]+)?", srcset)
                )
            for candidate in candidates:
                try:
                    url = urljoin(base_url, candidate)
                    parts = urlsplit(url)
                except ValueError:
                    # A malformed image URL must not abort the page check.
                    continue
                if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
                    continue
                # Fragments do not identify a different image resource.
                url = parts._replace(fragment="").geturl()
                extension = unquote(parts.path).rsplit("/", 1)[-1].rsplit(".", 1)[-1].lower()
                name = {"jpg": "JPEG", "jpeg": "JPEG", "tif": "TIFF", "tiff": "TIFF"}.get(extension)
                if name is None:
                    name = next((f for f in IMAGE_FORMATS[:-1] if f.lower() == extension), "Другие")
                grouped[name][url] = None
    result = {}
    for name, urls in grouped.items():
        result[f"{name}: количество"] = str(len(urls))
        result[f"{name}: ссылки на изображения"] = ", ".join(urls)
    return result
