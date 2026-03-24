"""Unit tests for get_user_profile."""

import pytest

from hn_pulse.tools.users import get_user_profile
from tests.conftest import MOCK_USER

HN_BASE = "https://hacker-news.firebaseio.com/v0"


@pytest.mark.asyncio
async def test_get_user_profile_returns_core_fields(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/user/rustlang.json", json=MOCK_USER)

    result = await get_user_profile(username="rustlang")

    assert result["id"] == "rustlang"
    assert result["karma"] == 9999
    assert result["about"] == "Official Rust Language account"
    assert "recent_submissions" not in result


@pytest.mark.asyncio
async def test_get_user_profile_includes_recent_submissions(httpx_mock):
    httpx_mock.add_response(url=f"{HN_BASE}/user/rustlang.json", json=MOCK_USER)

    result = await get_user_profile(username="rustlang", include_recent_submissions=True)

    assert "recent_submissions" in result
    assert len(result["recent_submissions"]) == 10


@pytest.mark.asyncio
async def test_get_user_profile_truncates_submissions_to_10(httpx_mock):
    user_with_many = {**MOCK_USER, "submitted": list(range(1, 1000))}
    httpx_mock.add_response(url=f"{HN_BASE}/user/prolific.json", json=user_with_many)

    result = await get_user_profile(username="prolific", include_recent_submissions=True)
    assert len(result["recent_submissions"]) == 10


@pytest.mark.asyncio
async def test_get_user_profile_returns_error_for_missing_user(httpx_mock):
    httpx_mock.add_response(
        url=f"{HN_BASE}/user/nobody123.json",
        content=b"null",
        headers={"content-type": "application/json"},
    )

    result = await get_user_profile(username="nobody123")
    assert "error" in result
    assert "nobody123" in result["error"]


@pytest.mark.asyncio
async def test_get_user_profile_handles_missing_optional_fields(httpx_mock):
    sparse_user = {"id": "sparse_user", "karma": 0}
    httpx_mock.add_response(url=f"{HN_BASE}/user/sparse_user.json", json=sparse_user)

    result = await get_user_profile(username="sparse_user")
    assert result["karma"] == 0
    assert result["about"] == ""
    assert result["created"] is None
