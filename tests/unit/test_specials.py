"""Unit tests for get_job_listings, get_ask_hn, and get_show_hn."""

import pytest

from hn_pulse.tools.specials import get_ask_hn, get_job_listings, get_show_hn
from tests.conftest import MOCK_JOB, MOCK_STORY

HN_BASE = "https://hacker-news.firebaseio.com/v0"


@pytest.mark.asyncio
async def test_get_job_listings_returns_jobs(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/jobstories.json", json=[55555])
    httpx_mock.add_response(url=f"{HN_BASE}/item/55555.json", json=MOCK_JOB)

    result = await get_job_listings(count=1)
    assert len(result) == 1
    assert result[0]["type"] == "job"
    assert "Rust Engineer" in result[0]["title"]


@pytest.mark.asyncio
async def test_get_job_listings_clamps_count(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/jobstories.json", json=list(range(1, 100)))
    for i in range(1, 21):
        httpx_mock.add_response(
            url=f"{HN_BASE}/item/{i}.json",
            json={**MOCK_JOB, "id": i},
        )

    result = await get_job_listings(count=999)
    assert len(result) == 20


@pytest.mark.asyncio
async def test_get_ask_hn_returns_ask_stories(httpx_mock):
    ask_story = {**MOCK_STORY, "id": 11111, "title": "Ask HN: Best resources for Rust?"}
    httpx_mock.add_response(url=f"{HN_BASE}/askstories.json", json=[11111])
    httpx_mock.add_response(url=f"{HN_BASE}/item/11111.json", json=ask_story)

    result = await get_ask_hn(count=1)
    assert len(result) == 1
    assert "Ask HN" in result[0]["title"]


@pytest.mark.asyncio
async def test_get_show_hn_returns_show_stories(httpx_mock):
    show_story = {**MOCK_STORY, "id": 22222, "title": "Show HN: I built a Rust MCP server"}
    httpx_mock.add_response(url=f"{HN_BASE}/showstories.json", json=[22222])
    httpx_mock.add_response(url=f"{HN_BASE}/item/22222.json", json=show_story)

    result = await get_show_hn(count=1)
    assert len(result) == 1
    assert "Show HN" in result[0]["title"]


@pytest.mark.asyncio
async def test_specials_filter_none_items(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/jobstories.json", json=[55555, 66666])
    httpx_mock.add_response(url=f"{HN_BASE}/item/55555.json", json=MOCK_JOB)
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/66666.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )

    result = await get_job_listings(count=2)
    assert len(result) == 1
    assert result[0]["id"] == 55555
