import httpx

from ...context import CheckContext
from ...network.fetcher import fetch_with_retries


async def check_sitemap(ctx: CheckContext) -> str:
    base_url = ctx.final_url if ctx.final_url else ctx.normalized_url
    sitemap_url = base_url.rstrip("/") + "/sitemap.xml"
    resp = await fetch_with_retries(ctx.client, sitemap_url, ctx.runtime)
    if not resp:
        return "нет ответа"
    return "200" if resp.status_code == 200 else str(resp.status_code)
