from urllib.parse import urlparse, urlunparse


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc or parsed.path
    path = parsed.path if parsed.netloc else ""
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path or "/")
    return urlunparse(normalized)
