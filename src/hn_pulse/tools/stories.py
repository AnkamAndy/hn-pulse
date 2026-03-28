"""Top and new story feed tools."""

import logging
from typing import Annotated, cast

from hn_pulse.client import hn_client
from hn_pulse.hn_types import Story
from hn_pulse.tools.common import MAX_STORY_COUNT, fetch_item, gather_items

logger = logging.getLogger(__name__)


async def get_top_stories(
    count: Annotated[int, "Number of top stories to return (1-30)"] = 10,
) -> list[Story]:
    """Fetch the current top stories from Hacker News, ranked by score and recency."""
    count = max(1, min(count, MAX_STORY_COUNT))
    async with hn_client() as client:
        r = await client.get("/topstories.json")
        r.raise_for_status()
        ids: list[int] = r.json()[:count]
        logger.debug("fetching %d top stories", len(ids))
        items = await gather_items([fetch_item(client, i) for i in ids], "top_stories")
        return cast(list[Story], items)


async def get_new_stories(
    count: Annotated[int, "Number of new stories to return (1-30)"] = 10,
) -> list[Story]:
    """Fetch the most recently submitted stories from Hacker News."""
    count = max(1, min(count, MAX_STORY_COUNT))
    async with hn_client() as client:
        r = await client.get("/newstories.json")
        r.raise_for_status()
        ids: list[int] = r.json()[:count]
        logger.debug("fetching %d new stories", len(ids))
        items = await gather_items([fetch_item(client, i) for i in ids], "new_stories")
        return cast(list[Story], items)
