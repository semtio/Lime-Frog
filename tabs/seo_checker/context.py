from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from .config import CheckOptions, RuntimeOptions
from .network.link_cache import LinkCheckCache


@dataclass
class CheckContext:
    """Унифицированный контекст для проверки одного URL."""

    raw_url: str
    normalized_url: str
    response_no_follow: Optional[httpx.Response]
    response: Optional[httpx.Response]
    soup: Optional[BeautifulSoup]
    client: httpx.AsyncClient
    check_options: CheckOptions
    runtime: RuntimeOptions
    final_url: Optional[str] = None
    is_redirect: bool = False
    link_cache: Optional[LinkCheckCache] = None
