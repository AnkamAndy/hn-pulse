"""Error scenario tests — network failures, HTTP errors, malformed responses."""

import logging
import re

import httpx
import pytest

from hn_pulse.client import hn_client
from hn_pulse.tools.common import fetch_item
from hn_pulse.tools.search import search_stories
from hn_pulse.tools.specials import get_job_listings
from hn_pulse.tools.stories import get_top_stories
from hn_pulse.tools.users import get_user_profile

HN_BASE = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_BASE = "https://hn.algolia.com/api/v1"

# pytest-httpx 0.30+ requires re.compile() patterns to match URLs with query params
ALGOLIA_SEARCH = re.compile(r"https://hn\.algolia\.com/api/v1/search\?")


# ── get_top_stories: feed endpoint failure ───────────────────────────

@pytest.mark.asyncio
async def test_get_top_stories_raises_on_feed_503(httpx_mock):
    """HTTP 503 from the feed endpoint should propagate as HTTPStatusError."""
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", status_code=503)
    with pytest.raises(httpx.HTTPStatusError):
        await get_top_stories(count=5)


@pytest.mark.asyncio
async def test_get_top_stories_raises_on_feed_500(httpx_mock):
    """HTTP 500 from the feed endpoint should propagate as HTTPStatusError."""
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", status_code=500)
    with pytest.raises(httpx.HTTPStatusError):
        await get_top_stories(count=3)


# ── fetch_item: per-item errors are swallowed, not raised ────────────

@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_404(httpx_mock):
    """404 from a single item should return None, not raise."""
    httpx_mock.add_response(url=f"{HN_BASE}/item/99999.json", status_code=404)
    async with hn_client() as client:
        result = await fetch_item(client, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_503(httpx_mock):
    """503 from a single item should return None, not raise."""
    httpx_mock.add_response(url=f"{HN_BASE}/item/99999.json", status_code=503)
    async with hn_client() as client:
        result = await fetch_item(client, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_null_body(httpx_mock):
    """JSON null body (deleted item) should return None."""
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99999.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )
    async with hn_client() as client:
        result = await fetch_item(client, 99999)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_item_returns_none_on_non_json_response(httpx_mock):
    """Non-JSON response body (e.g. HTML error page) should return None."""
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/12345.json",
        status_code=200,
        content=b"<html><body>Service Unavailable</body></html>",
        headers={"content-type": "text/html"},
    )
    async with hn_client() as client:
        result = await fetch_item(client, 12345)
    assert result is None


# ── gather_items: logs failure rate ─────────────────────────────────

@pytest.mark.asyncio
async def test_gather_items_logs_failures(httpx_mock, caplog):
    """gather_items should log when some items are unavailable."""
    httpx_mock.add_response(
        url=f"{HN_BASE}/topstories.json", json=[10001, 10002]
    )
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/10001.json",
        json={"id": 10001, "type": "story", "title": "OK"},
    )
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/10002.json", status_code=404
    )

    with caplog.at_level(logging.INFO, logger="hn_pulse.tools.common"):
        result = await get_top_stories(count=2)

    assert len(result) == 1
    assert "1/2 items unavailable" in caplog.text


# ── get_job_listings: feed error propagates ──────────────────────────

@pytest.mark.asyncio
async def test_get_job_listings_raises_on_feed_error(httpx_mock):
    """HTTP 503 from job feed should propagate as HTTPStatusError."""
    httpx_mock.add_response(url=f"{HN_BASE}/jobstories.json", status_code=503)
    with pytest.raises(httpx.HTTPStatusError):
        await get_job_listings(count=5)


# ── search_stories: Algolia errors ──────────────────────────────────

@pytest.mark.asyncio
async def test_search_raises_on_algolia_429(httpx_mock):
    """Algolia 429 rate limit should propagate as HTTPStatusError."""
    httpx_mock.add_response(
        url=ALGOLIA_SEARCH,
        status_code=429,
        content=b"",
    )
    with pytest.raises(httpx.HTTPStatusError):
        await search_stories(query="rust")


@pytest.mark.asyncio
async def test_search_raises_on_algolia_500(httpx_mock):
    """Algolia 500 should propagate as HTTPStatusError."""
    httpx_mock.add_response(
        url=ALGOLIA_SEARCH,
        status_code=500,
        content=b"",
    )
    with pytest.raises(httpx.HTTPStatusError):
        await search_stories(query="python")


# ── get_user_profile: missing user ──────────────────────────────────

@pytest.mark.asyncio
async def test_get_user_profile_returns_error_on_null_user(httpx_mock):
    """Null JSON body for unknown user should return an error dict, not raise."""
    httpx_mock.add_response(
        url=f"{HN_BASE}/user/nonexistent_xyz.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )
    result = await get_user_profile(username="nonexistent_xyz")
    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_profile_raises_on_http_error(httpx_mock):
    """HTTP 500 from user endpoint should propagate as HTTPStatusError."""
    httpx_mock.add_response(
        url=f"{HN_BASE}/user/anyuser.json",
        status_code=500,
    )
    with pytest.raises(httpx.HTTPStatusError):
        await get_user_profile(username="anyuser")
