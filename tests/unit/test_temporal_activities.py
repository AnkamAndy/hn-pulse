"""Unit tests for Temporal activity wrappers.

Activities are tested via ActivityEnvironment — no live Temporal server needed.
HTTP calls are intercepted by pytest-httpx (same pattern as other unit tests).
"""

import re

import httpx
import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from temporal.activities import (
    get_ask_hn,
    get_new_stories,
    get_show_hn,
    get_story_details,
    get_top_stories,
    search_stories,
)
from tests.conftest import MOCK_ALGOLIA_RESPONSE, MOCK_COMMENT, MOCK_STORY

HN_BASE = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_SEARCH = re.compile(r"https://hn\.algolia\.com/api/v1/search\?")


@pytest.fixture
def env() -> ActivityEnvironment:
    return ActivityEnvironment()


# ── get_top_stories ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_top_stories_returns_stories(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", json=[12345])
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=MOCK_STORY)

    result = await env.run(get_top_stories, 1)

    assert len(result) == 1
    assert result[0]["id"] == 12345


@pytest.mark.asyncio
async def test_get_top_stories_404_raises_non_retryable(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", status_code=404)

    with pytest.raises(ApplicationError) as exc_info:
        await env.run(get_top_stories, 5)

    assert exc_info.value.non_retryable is True


@pytest.mark.asyncio
async def test_get_top_stories_503_raises_retryable(env, httpx_mock):
    """503 propagates as a plain HTTPStatusError — Temporal will retry it."""
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", status_code=503)

    with pytest.raises(httpx.HTTPStatusError):
        await env.run(get_top_stories, 5)


# ── get_new_stories ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_new_stories_returns_stories(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/newstories.json", json=[99001])
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99001.json",
        json={**MOCK_STORY, "id": 99001, "title": "Brand New Story"},
    )

    result = await env.run(get_new_stories, 1)

    assert len(result) == 1
    assert result[0]["title"] == "Brand New Story"


@pytest.mark.asyncio
async def test_get_new_stories_404_raises_non_retryable(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/newstories.json", status_code=404)

    with pytest.raises(ApplicationError) as exc_info:
        await env.run(get_new_stories, 5)

    assert exc_info.value.non_retryable is True


# ── search_stories ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_stories_returns_hits(env, httpx_mock):
    httpx_mock.add_response(url=ALGOLIA_SEARCH, json=MOCK_ALGOLIA_RESPONSE)

    result = await env.run(search_stories, "rust", "relevance", "story", 2, 0)

    assert result["query"] == "rust"
    assert len(result["hits"]) == 2
    assert result["hits"][0]["story_id"] == "12345"


@pytest.mark.asyncio
async def test_search_stories_404_raises_non_retryable(env, httpx_mock):
    httpx_mock.add_response(url=ALGOLIA_SEARCH, status_code=404, content=b"")

    with pytest.raises(ApplicationError) as exc_info:
        await env.run(search_stories, "rust", "relevance", "story", 5, 0)

    assert exc_info.value.non_retryable is True


@pytest.mark.asyncio
async def test_search_stories_429_is_retryable(env, httpx_mock):
    """429 propagates as HTTPStatusError — Temporal will retry it."""
    httpx_mock.add_response(url=ALGOLIA_SEARCH, status_code=429, content=b"")

    with pytest.raises(httpx.HTTPStatusError):
        await env.run(search_stories, "rust", "relevance", "story", 5, 0)


# ── get_story_details ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_story_details_returns_story_with_comments(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=MOCK_STORY)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99001.json", json=MOCK_COMMENT)
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99002.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99003.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )

    result = await env.run(get_story_details, 12345, 5, False)

    assert result["id"] == 12345
    assert result["title"] == MOCK_STORY["title"]


@pytest.mark.asyncio
async def test_get_story_details_404_raises_non_retryable(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/item/99999.json", status_code=404)

    with pytest.raises(ApplicationError) as exc_info:
        await env.run(get_story_details, 99999, 5, False)

    assert exc_info.value.non_retryable is True


# ── get_ask_hn / get_show_hn ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_ask_hn_returns_stories(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/askstories.json", json=[12345])
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/12345.json",
        json={**MOCK_STORY, "title": "Ask HN: How do you learn Rust?"},
    )

    result = await env.run(get_ask_hn, 1)

    assert len(result) == 1
    assert "Ask HN" in result[0]["title"]


@pytest.mark.asyncio
async def test_get_show_hn_returns_stories(env, httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/showstories.json", json=[12345])
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/12345.json",
        json={**MOCK_STORY, "title": "Show HN: My open-source project"},
    )

    result = await env.run(get_show_hn, 1)

    assert len(result) == 1
    assert "Show HN" in result[0]["title"]
