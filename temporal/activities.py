"""HN Pulse Temporal activities.

Thin @activity.defn wrappers around the existing async tool functions.
Activities are the retriable, timeout-able units of work in Temporal.

Each activity calls the underlying tool function directly (no MCP subprocess)
since the worker has hn_pulse and hn_extras installed as packages.

404 responses are converted to non-retryable ApplicationError so Temporal
doesn't burn retries on definitively missing resources. All other HTTP errors
(429, 503, etc.) propagate as retryable — Temporal's retry policy handles them.
"""

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from hn_extras.fetch import fetch_article as _fetch_article
from hn_pulse.tools.item import get_story_details as _get_story_details
from hn_pulse.tools.search import search_stories as _search_stories
from hn_pulse.tools.specials import get_ask_hn as _get_ask_hn
from hn_pulse.tools.specials import get_show_hn as _get_show_hn
from hn_pulse.tools.stories import get_new_stories as _get_new_stories
from hn_pulse.tools.stories import get_top_stories as _get_top_stories
from hn_pulse.tools.users import get_user_profile as _get_user_profile


def _non_retryable_404(exc: httpx.HTTPStatusError, label: str) -> ApplicationError:
    return ApplicationError(f"{label} returned 404", non_retryable=True)


@activity.defn
async def get_top_stories(count: int = 10) -> list[dict]:
    activity.logger.info("get_top_stories count=%d", count)
    try:
        return await _get_top_stories(count=count)  # type: ignore[return-value]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise _non_retryable_404(exc, "HN top stories endpoint") from exc
        raise


@activity.defn
async def get_new_stories(count: int = 10) -> list[dict]:
    activity.logger.info("get_new_stories count=%d", count)
    try:
        return await _get_new_stories(count=count)  # type: ignore[return-value]
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise _non_retryable_404(exc, "HN new stories endpoint") from exc
        raise


@activity.defn
async def search_stories(
    query: str,
    sort_by: str = "relevance",
    tags: str = "story",
    num_results: int = 10,
    page: int = 0,
) -> dict:
    activity.logger.info("search_stories query=%r num_results=%d", query, num_results)
    try:
        return await _search_stories(  # type: ignore[return-value]
            query=query,
            sort_by=sort_by,  # type: ignore[arg-type]
            tags=tags,
            num_results=num_results,
            page=page,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise _non_retryable_404(exc, "Algolia search endpoint") from exc
        raise


@activity.defn
async def get_story_details(
    story_id: int,
    max_comments: int = 5,
    include_replies: bool = False,
) -> dict:
    activity.logger.info("get_story_details story_id=%d", story_id)
    try:
        return await _get_story_details(  # type: ignore[return-value]
            story_id=story_id,
            max_comments=max_comments,
            include_replies=include_replies,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise _non_retryable_404(exc, f"Story {story_id}") from exc
        raise


@activity.defn
async def fetch_article(url: str, max_chars: int = 4000) -> dict:
    activity.logger.info("fetch_article url=%s", url)
    try:
        return await _fetch_article(url=url, max_chars=max_chars)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise _non_retryable_404(exc, f"Article {url}") from exc
        raise


@activity.defn
async def get_user_profile(username: str, include_recent_submissions: bool = False) -> dict:
    activity.logger.info("get_user_profile username=%s", username)
    try:
        return await _get_user_profile(  # type: ignore[return-value]
            username=username,
            include_recent_submissions=include_recent_submissions,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise _non_retryable_404(exc, f"User '{username}'") from exc
        raise


@activity.defn
async def get_ask_hn(count: int = 5) -> list[dict]:
    activity.logger.info("get_ask_hn count=%d", count)
    return await _get_ask_hn(count=count)  # type: ignore[return-value]


@activity.defn
async def get_show_hn(count: int = 5) -> list[dict]:
    activity.logger.info("get_show_hn count=%d", count)
    return await _get_show_hn(count=count)  # type: ignore[return-value]
