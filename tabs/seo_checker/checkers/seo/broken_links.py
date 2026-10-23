"""Check unique references from the page without downloading resource bodies."""
import asyncio
import re
from urllib.parse import urljoin, urlsplit

import httpx

from ...context import CheckContext


def collect_link_urls(ctx: CheckContext) -> list[str]:
    if ctx.soup is None:
        return []
    base_url = str(ctx.response.url) if ctx.response is not None else ctx.final_url or ctx.normalized_url
    base = ctx.soup.find('base', href=True)
    if base:
        try:
            base_url = urljoin(base_url, base['href'])
        except ValueError:
            pass
    urls = {}
    for tag in ctx.soup.find_all(['a', 'area', 'img', 'script', 'link', 'source']):
        candidates = []
        if tag.name in ('a', 'area'):
            candidates.append(tag.get('href', ''))
        elif tag.name == 'link':
            if set(tag.get('rel', [])) & {'stylesheet', 'icon', 'preload', 'modulepreload'}:
                candidates.append(tag.get('href', ''))
        else:
            candidates.append(tag.get('src', ''))
        if tag.name in ('img', 'source'):
            candidates.extend(tag.get(attr, '') for attr in ('data-src', 'data-original', 'data-lazy-src'))
            for attr in ('srcset', 'data-srcset', 'data-lazy-srcset'):
                candidates.extend(m.group(1).rstrip(',') for m in re.finditer(
                    r'(?:^|\s|,\s*)([^\s]+)(?:\s+[^,]+)?', tag.get(attr, '')))
        for candidate in candidates:
            candidate = candidate.strip()
            if not candidate or candidate.startswith('#'):
                continue
            try:
                parts = urlsplit(urljoin(base_url, candidate))
            except ValueError:
                continue
            if parts.scheme.lower() in ('http', 'https') and parts.netloc:
                urls[parts._replace(fragment='').geturl()] = None
    return list(urls)


async def check_broken_links(ctx: CheckContext) -> str:
    if ctx.soup is None:
        return 'нет HTML'
    semaphore = asyncio.Semaphore(max(1, min(ctx.runtime.concurrency, 10)))

    async def check(url):
        async with semaphore:
            for attempt in range(ctx.runtime.retries + 1):
                try:
                    # GET avoids false failures from servers that reject HEAD.
                    # Close after response headers; image/script bodies are not read.
                    async with ctx.client.stream('GET', url, follow_redirects=True,
                                                 timeout=ctx.runtime.timeout_seconds) as response:
                        code = response.status_code
                        if code >= 400 or 300 <= code < 400:
                            return f'{code}: {url}'
                        return None
                except httpx.TimeoutException:
                    error = 'таймаут'
                except httpx.TooManyRedirects:
                    return f'цикл редиректов: {url}'
                except (httpx.HTTPError, ValueError):
                    error = 'ошибка соединения'
                if attempt < ctx.runtime.retries:
                    await asyncio.sleep(0.25)
            return f'{error}: {url}'

    cache = getattr(ctx, 'link_cache', None)

    async def cached_check(url):
        if cache is None:
            return await check(url)
        return await cache.get(url, lambda: check(url))

    results = await asyncio.gather(*(cached_check(url) for url in collect_link_urls(ctx)))
    failures = [item for item in results if item is not None]
    return ', '.join([str(len(failures)), *failures])
