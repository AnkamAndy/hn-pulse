"""Unit tests for get_story_details."""

import pytest

from hn_pulse.tools.item import get_story_details
from tests.conftest import MOCK_COMMENT, MOCK_DEAD_COMMENT, MOCK_DELETED_COMMENT, MOCK_STORY

HN_BASE = "https://hacker-news.firebaseio.com/v0"


@pytest.mark.asyncio
async def test_get_story_details_returns_story_with_comments(httpx_mock):
    story = {**MOCK_STORY, "kids": [99001]}
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=story)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99001.json", json=MOCK_COMMENT)

    result = await get_story_details(story_id=12345, max_comments=5)

    assert result["id"] == 12345
    assert result["title"] == MOCK_STORY["title"]
    assert len(result["comments"]) == 1
    assert result["comments"][0]["text"] == MOCK_COMMENT["text"]
    # kids key should be stripped (already in comments)
    assert "kids" not in result


@pytest.mark.asyncio
async def test_get_story_details_filters_deleted_comments(httpx_mock):
    story = {**MOCK_STORY, "kids": [99001, 99002]}
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=story)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99001.json", json=MOCK_COMMENT)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99002.json", json=MOCK_DELETED_COMMENT)

    result = await get_story_details(story_id=12345, max_comments=10)
    assert len(result["comments"]) == 1
    assert result["comments"][0]["id"] == MOCK_COMMENT["id"]


@pytest.mark.asyncio
async def test_get_story_details_filters_dead_comments(httpx_mock):
    story = {**MOCK_STORY, "kids": [99001, 99003]}
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=story)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99001.json", json=MOCK_COMMENT)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99003.json", json=MOCK_DEAD_COMMENT)

    result = await get_story_details(story_id=12345, max_comments=10)
    assert len(result["comments"]) == 1


@pytest.mark.asyncio
async def test_get_story_details_returns_error_for_missing_story(httpx_mock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/item/99999.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )

    result = await get_story_details(story_id=99999)
    assert "error" in result
    assert "99999" in result["error"]


@pytest.mark.asyncio
async def test_get_story_details_clamps_max_comments(httpx_mock):
    # Story has 5 kids but max_comments=2 → only 2 fetched
    kids = [10001, 10002, 10003, 10004, 10005]
    story = {**MOCK_STORY, "kids": kids}
    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=story)
    for k in kids[:2]:
        httpx_mock.add_response(
            url=f"{HN_BASE}/item/{k}.json",
            json={**MOCK_COMMENT, "id": k},
        )

    result = await get_story_details(story_id=12345, max_comments=2)
    assert len(result["comments"]) == 2


@pytest.mark.asyncio
async def test_get_story_details_includes_replies_when_requested(httpx_mock):
    story = {**MOCK_STORY, "kids": [99001]}
    comment_with_kid = {**MOCK_COMMENT, "id": 99001, "kids": [99010]}
    reply = {**MOCK_COMMENT, "id": 99010, "text": "A reply", "parent": 99001}

    httpx_mock.add_response(url=f"{HN_BASE}/item/12345.json", json=story)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99001.json", json=comment_with_kid)
    httpx_mock.add_response(url=f"{HN_BASE}/item/99010.json", json=reply)

    result = await get_story_details(story_id=12345, max_comments=5, include_replies=True)
    assert "replies" in result["comments"][0]
    assert result["comments"][0]["replies"][0]["id"] == 99010
