"""Unit tests for get_top_stories and get_new_stories."""

import pytest

from hn_pulse.tools.stories import get_new_stories, get_top_stories
from tests.conftest import MOCK_STORY

HN_BASE = "https://hacker-news.firebaseio.com/v0"


@pytest.mark.asyncio
async def test_get_top_stories_returns_stories(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", json=[12345, 67890])
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/12345.json",
        json={**MOCK_STORY, "id": 12345, "title": "Story A"},
    )
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/67890.json",
        json={**MOCK_STORY, "id": 67890, "title": "Story B"},
    )

    result = await get_top_stories(count=2)

    assert len(result) == 2
    assert result[0]["title"] == "Story A"
    assert result[1]["title"] == "Story B"


@pytest.mark.asyncio
async def test_get_top_stories_clamps_count_to_30(httpx_mock):
    # Feed returns 500 IDs; only 30 should be fetched
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", json=list(range(1, 501)))
    for i in range(1, 31):
        httpx_mock.add_response(
            url=f"{HN_BASE}/item/{i}.json",
            json={**MOCK_STORY, "id": i, "title": f"Story {i}"},
        )

    result = await get_top_stories(count=999)
    assert len(result) == 30


@pytest.mark.asyncio
async def test_get_top_stories_clamps_count_to_minimum_1(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", json=[12345])
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=MOCK_STORY)

    result = await get_top_stories(count=-5)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_top_stories_filters_null_items(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/topstories.json", json=[12345, 99999])
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=MOCK_STORY)
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99999.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )

    result = await get_top_stories(count=2)
    assert len(result) == 1
    assert result[0]["id"] == 12345


@pytest.mark.asyncio
async def test_get_new_stories_returns_stories(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/newstories.json", json=[99001])
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99001.json",
        json={**MOCK_STORY, "id": 99001, "title": "Brand New Story"},
    )

    result = await get_new_stories(count=1)
    assert len(result) == 1
    assert result[0]["title"] == "Brand New Story"


@pytest.mark.asyncio
async def test_get_new_stories_clamps_count(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/newstories.json", json=list(range(1, 200)))
    for i in range(1, 31):
        httpx_mock.add_response(
            url=f"{HN_BASE}/item/{i}.json",
            json={**MOCK_STORY, "id": i},
        )

    result = await get_new_stories(count=50)
    assert len(result) == 30
