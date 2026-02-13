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
