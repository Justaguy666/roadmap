"""
Domain service: URL normalizer.

Normalizes URLs for strict deduplication:
  - Lowercases scheme and host
  - Strips standard default ports (:80, :443)
  - Strips tracking query parameters (utm_*, ref, source, fbclid, etc.)
  - Sorts remaining query parameters deterministically
  - Removes trailing slashes (except for root domain)
  - Removes fragments (#section)
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

STRIP_QUERY_PARAMS: set[str] = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_src",
    "fbclid",
    "gclid",
    "source",
}


def normalize_url(url: str) -> str:
    """Return a canonical, deduplicated representation of a URL."""
    if not url:
        return ""

    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    # Strip default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Normalize path
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter query parameters
    query_tuples = parse_qsl(parsed.query, keep_blank_values=False)
    filtered = [
        (k, v)
        for k, v in query_tuples
        if k.lower() not in STRIP_QUERY_PARAMS and not k.lower().startswith("utm_")
    ]
    filtered.sort(key=lambda x: x[0])
    query = urlencode(filtered)

    # Reconstruct without fragment
    return urlunparse((scheme, netloc, path, "", query, ""))
