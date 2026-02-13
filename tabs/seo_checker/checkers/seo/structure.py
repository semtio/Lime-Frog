from typing import List, Optional

from bs4 import BeautifulSoup

from ...context import CheckContext


def build_html_structure(ctx: CheckContext) -> str:
    soup = ctx.soup
    if not soup:
        return "нет данных"

    # Определяем какие теги отслеживать на основе настроек
    tags_to_track = []

    if ctx.check_options.html_track_headings:
        tags_to_track.extend(["h1", "h2", "h3", "h4", "h5", "h6"])

    if ctx.check_options.html_track_paragraphs:
        tags_to_track.append("p")

    if ctx.check_options.html_track_semantic:
        tags_to_track.extend(
            ["main", "section", "article", "header", "footer", "nav", "aside"]
        )

    if ctx.check_options.html_track_media:
        tags_to_track.extend(["figure", "figcaption"])

    if ctx.check_options.html_track_other:
        tags_to_track.extend(["address", "time"])

    if not tags_to_track:
        return "нет выбранных тегов"

    sequence: List[str] = []
    for tag in soup.find_all(tags_to_track):
        sequence.append(tag.name.upper())
    return ">".join(sequence) if sequence else "нет структурных элементов"
