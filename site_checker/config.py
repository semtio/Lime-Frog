from dataclasses import dataclass, field
from typing import Dict


@dataclass
class CheckOptions:
    check_status_codes: bool = True
    check_redirects: bool = True
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
}

DEFAULT_CHECK_OPTIONS = CheckOptions()
DEFAULT_RUNTIME_OPTIONS = RuntimeOptions()
