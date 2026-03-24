"""Shared HTTP client factory for HN Firebase and Algolia Search APIs."""

import httpx

HN_BASE = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_BASE = "https://hn.algolia.com/api/v1"

_TIMEOUT = 10.0


def hn_client() -> httpx.AsyncClient:
    """Return an async client pre-configured for the HN Firebase API."""
    return httpx.AsyncClient(
        base_url=HN_BASE,
        timeout=_TIMEOUT,
        headers={"Accept": "application/json"},
    )


def algolia_client() -> httpx.AsyncClient:
    """Return an async client pre-configured for the Algolia HN Search API."""
    return httpx.AsyncClient(
        base_url=ALGOLIA_BASE,
        timeout=_TIMEOUT,
        headers={"Accept": "application/json"},
    )
