from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CheckOptions:
    check_status_codes: bool = True
    check_redirects: bool = True
    check_html_lang: bool = True
    check_indexability: bool = True
    check_titles: bool = True
    check_sitemap: bool = True
    check_robots: bool = True
    check_404: bool = True
    check_h1: bool = True
    check_images: bool = True
    check_html_structure: bool = True
    check_heading_duplicates: bool = True
    follow_redirects_for_checks: bool = False  # По умолчанию НЕ проверяем конечные URL

    # Настройки HTML структуры: какие теги отслеживать
    html_track_headings: bool = True  # H1-H6
    html_track_paragraphs: bool = True  # P
    html_track_semantic: bool = (
        True  # main, section, article, header, footer, nav, aside
    )
    html_track_media: bool = False  # figure, figcaption
    html_track_other: bool = False  # address, time

    def to_dict(self) -> Dict[str, bool]:
        return self.__dict__.copy()


@dataclass
class RuntimeOptions:
    timeout_seconds: int = 15
    retries: int = 2
    concurrency: int = 3


CHECK_LABELS = {
    "check_status_codes": "Коды ответов",
    "check_redirects": "Редиректы",
    "check_html_lang": "Язык сайта (HTML lang)",
    "check_indexability": "Indexability (noindex/nofollow, canonical)",
    "check_titles": "Title / Description",
    "check_sitemap": "Sitemap.xml",
    "check_robots": "Robots.txt",
    "check_404": "Страница 404",
    "check_h1": "H1",
    "check_images": "Alt изображений",
    "check_html_structure": "HTML структура (Hn, P)",
    "check_heading_duplicates": "Дубли H1/H2/H3",
    "follow_redirects_for_checks": "Проверять конечные URL после редиректов",
    # Настройки HTML структуры
    "html_track_headings": "Заголовки (H1-H6)",
    "html_track_paragraphs": "Параграфы (P)",
    "html_track_semantic": "Семантика (main, section, article, header, footer, nav, aside)",
    "html_track_media": "Медиа (figure, figcaption)",
    "html_track_other": "Другое (address, time)",
}

DEFAULT_CHECK_OPTIONS = CheckOptions()
DEFAULT_RUNTIME_OPTIONS = RuntimeOptions()
