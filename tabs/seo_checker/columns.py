"""Stable output groups shared by settings, result rows and exports."""
from .checkers.seo.images import IMAGE_FORMAT_COLUMNS

COLUMN_GROUPS = {
    'check_status_codes': ['Код ответа'],
    'check_redirects': ['Редирект'],
    'check_html_lang': ['Язык сайта'],
    'check_indexability': ['Noindex', 'Nofollow', 'Canonical'],
    'check_titles': ['Title', 'Title Длина', 'Description', 'Description Длина'],
    'check_sitemap': ['Sitemap 200'],
    'check_pages_from_sitemap': ['Страницы сайта'],
    'check_robots': ['Robots 200', 'Robots Disallow', 'Robots Sitemap'],
    'check_404': ['Ссылка на стр.404', 'Код стр.404', 'Корректность 404'],
    'check_h1': ['Кол-во H1'],
    'headings': ['H1', 'H2', 'H3', 'H4', 'H5', 'H6'],
    'check_html_structure': ['HTML структура'],
    'check_heading_duplicates': ['Дубли H1/H2/H3'],
    'check_cms': ['CMS'],
    'check_broken_links': ['Битые ссылки'],
    'check_image_formats': IMAGE_FORMAT_COLUMNS,
    'check_images': ['Кол-во img', 'Кол-во alt'],
}


def normalize_column_order(value):
    order = []
    if isinstance(value, list):
        for key in value:
            if isinstance(key, str) and key in COLUMN_GROUPS and key not in order:
                order.append(key)
    return order + [key for key in COLUMN_GROUPS if key not in order]


def order_columns(columns, order):
    available = set(columns)
    result = ['URL'] if 'URL' in available else []
    for key in normalize_column_order(order):
        group = list(COLUMN_GROUPS[key])
        if key == 'check_images':
            group += sorted((col for col in columns if col.startswith('Alt-')),
                            key=lambda col: int(col[4:]))
        result.extend(col for col in group if col in available)
    return result + [col for col in columns if col not in result]
