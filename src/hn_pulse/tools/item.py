"""Story detail and comment tree tool."""

import asyncio
import logging
from typing import Annotated

import httpx

from hn_pulse.client import hn_client
from hn_pulse.tools.common import MAX_COMMENTS, MAX_REPLY_CHILDREN
from hn_pulse.types import Comment, Story

logger = logging.getLogger(__name__)


async def _fetch_comment(
    client: httpx.AsyncClient,
    comment_id: int,
    include_replies: bool,
) -> Comment | None:
    """Fetch a comment, filtering out deleted/dead items."""
    try:
        r = await client.get(f"/item/{comment_id}.json")
        if r.status_code != 200:
            return None
    except httpx.HTTPError:
        return None

    comment = r.json()
    if not comment or comment.get("deleted") or comment.get("dead"):
        return None

    if include_replies and comment.get("kids"):
        child_ids: list[int] = comment["kids"][:MAX_REPLY_CHILDREN]
        replies = await asyncio.gather(
            *[_fetch_comment(client, k, False) for k in child_ids]
        )
        comment["replies"] = [rep for rep in replies if rep]

    return comment


async def get_story_details(
    story_id: Annotated[int, "The numeric Hacker News story ID"],
    max_comments: Annotated[int, "Maximum top-level comments to include (1-20)"] = 10,
    include_replies: Annotated[bool, "Whether to include replies under each top comment"] = False,
) -> Story:
    """Get full details of a Hacker News story including title, URL, score, and top comments."""
    max_comments = max(1, min(max_comments, MAX_COMMENTS))
    async with hn_client() as client:
        r = await client.get(f"/item/{story_id}.json")
        r.raise_for_status()
        story = r.json()
        if not story:
            return {"error": f"Story {story_id} not found"}  # type: ignore[return-value]

        kid_ids: list[int] = story.get("kids", [])[:max_comments]
        comments = await asyncio.gather(
            *[_fetch_comment(client, k, include_replies) for k in kid_ids]
        )
        valid_comments = [c for c in comments if c]
        filtered = len(kid_ids) - len(valid_comments)
        if filtered:
            logger.debug("filtered %d dead/deleted comments from story %d", filtered, story_id)
        story["comments"] = valid_comments
        # Remove raw kids list to avoid duplicating data
        story.pop("kids", None)
        return story
