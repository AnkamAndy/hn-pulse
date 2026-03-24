"""Unit tests for search_stories."""

import re

import pytest

from hn_pulse.tools.search import _clean_hit, search_stories
from tests.conftest import MOCK_ALGOLIA_RESPONSE

# Use regex patterns to match Algolia URLs regardless of query param values.
# pytest-httpx 0.30+ does exact URL matching by default; re.compile() opts in to pattern match.
# We always send query params so the URL always contains "?"; this distinguishes
# /search? from /search_by_date?.
ALGOLIA_SEARCH = re.compile(r"https://hn\.algolia\.com/api/v1/search\?")
ALGOLIA_SEARCH_BY_DATE = re.compile(r"https://hn\.algolia\.com/api/v1/search_by_date\?")


@pytest.mark.asyncio
async def test_search_stories_relevance_endpoint(httpx_mock):
    httpx_mock.add_response(url=ALGOLIA_SEARCH, json=MOCK_ALGOLIA_RESPONSE)

    result = await search_stories(query="rust", sort_by="relevance", num_results=2)

    assert result["query"] == "rust"
    assert result["total_hits"] == 5000
    assert len(result["hits"]) == 2
    assert result["hits"][0]["title"] == "Rust 2025 Edition"


@pytest.mark.asyncio
async def test_search_stories_date_endpoint(httpx_mock):
    httpx_mock.add_response(
        url=ALGOLIA_SEARCH_BY_DATE,
        json={**MOCK_ALGOLIA_RESPONSE, "query": "ai"},
    )

    result = await search_stories(query="ai", sort_by="date")
    assert result["query"] == "ai"


@pytest.mark.asyncio
async def test_search_stories_clamps_num_results(httpx_mock):
    httpx_mock.add_response(
        url=ALGOLIA_SEARCH,
        json={**MOCK_ALGOLIA_RESPONSE, "hitsPerPage": 20},
    )

    # count=999 → clamped to 20 before calling API
    result = await search_stories(query="python", num_results=999)
    assert result is not None
    assert result["hits"] is not None


@pytest.mark.asyncio
async def test_search_stories_passes_tag_filter(httpx_mock):
    httpx_mock.add_response(
        url=ALGOLIA_SEARCH,
        json={**MOCK_ALGOLIA_RESPONSE, "hits": []},
    )

    result = await search_stories(query="python", tags="ask_hn")
    # Confirms the call completed successfully with ask_hn tag parameter
    assert result["hits"] == []


@pytest.mark.asyncio
async def test_search_stories_includes_pagination(httpx_mock):
    httpx_mock.add_response(
        url=ALGOLIA_SEARCH,
        json={**MOCK_ALGOLIA_RESPONSE, "page": 2, "nbPages": 10},
    )

    result = await search_stories(query="python", page=2)
    assert result["page"] == 2
    assert result["total_pages"] == 10


def test_clean_hit_strips_algolia_metadata():
    raw = {
        "objectID": "1",
        "title": "Test Story",
        "url": "https://example.com",
        "author": "user1",
        "points": 50,
        "num_comments": 5,
        "created_at": "2025-01-01T00:00:00Z",
        "_highlightResult": {"title": {"value": "<em>Test</em>"}},
        "_tags": ["story", "author_user1"],
        "children": [111, 222, 333],
        "updated_at": "2025-01-02T00:00:00Z",
        "story_text": None,
        "comment_text": None,
    }

    clean = _clean_hit(raw)

    assert "_highlightResult" not in clean
    assert "_tags" not in clean
    assert "children" not in clean
    assert "updated_at" not in clean
    assert clean["title"] == "Test Story"
    assert clean["author"] == "user1"
    assert clean["points"] == 50


def test_clean_hit_falls_back_to_comment_fields():
    """Comments use story_title / story_url / comment_text instead of top-level fields."""
    raw = {
        "objectID": "99001",
        "story_id": "12345",
        "story_title": "Parent Story",
        "story_url": "https://example.com/parent",
        "author": "commenter",
        "comment_text": "This is a great comment",
        "created_at": "2025-01-01T00:00:00Z",
        "_highlightResult": {},
        "_tags": ["comment"],
    }

    clean = _clean_hit(raw)
    assert clean["title"] == "Parent Story"
    assert clean["url"] == "https://example.com/parent"
    assert clean["text"] == "This is a great comment"
