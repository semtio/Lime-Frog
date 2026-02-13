from typing import Dict

import httpx

from ...context import CheckContext
from ...network.fetcher import fetch_with_retries


async def check_robots(ctx: CheckContext) -> Dict[str, str]:
    base_url = ctx.final_url if ctx.final_url else ctx.normalized_url
    robots_url = base_url.rstrip("/") + "/robots.txt"
    resp = await fetch_with_retries(ctx.client, robots_url, ctx.runtime)
    result = {"Robots 200": "", "Robots Disallow": "", "Robots Sitemap": ""}
    if not resp:
        return result
    result["Robots 200"] = "200" if resp.status_code == 200 else str(resp.status_code)
    if resp.status_code == 200:
        body = resp.text.lower()
        # Собираем все Disallow директивы
        disallows = []
        for line in resp.text.split("\n"):
            line_lower = line.lower().strip()
            if line_lower.startswith("disallow:"):
                path = line[9:].strip()  # Берем после "disallow:"
                if path:
                    disallows.append(path)
        result["Robots Disallow"] = " | ".join(disallows) if disallows else ""
        result["Robots Sitemap"] = "да" if "sitemap: " in body else "нет"
    return result
