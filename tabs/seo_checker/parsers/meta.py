from typing import Optional, Tuple

import httpx
from bs4 import BeautifulSoup


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
