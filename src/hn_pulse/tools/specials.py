"""Job listings, Ask HN, and Show HN feed tools."""

import logging
from typing import Annotated, cast

from hn_pulse.client import hn_client
from hn_pulse.tools.common import MAX_SPECIAL_COUNT, fetch_item, gather_items
from hn_pulse.types import Story

logger = logging.getLogger(__name__)


async def _fetch_feed(endpoint: str, count: int) -> list[Story]:
    async with hn_client() as client:
        r = await client.get(endpoint)
        r.raise_for_status()
        ids: list[int] = r.json()[:count]
        logger.debug("fetching %d items from %s", len(ids), endpoint)
        return cast(list[Story], await gather_items([fetch_item(client, i) for i in ids], endpoint))


async def get_job_listings(
    count: Annotated[int, "Number of job listings to return (1-20)"] = 10,
) -> list[Story]:
    """Fetch current job postings from Hacker News (YC companies and community job posts)."""
    return await _fetch_feed("/jobstories.json", max(1, min(count, MAX_SPECIAL_COUNT)))


async def get_ask_hn(
    count: Annotated[int, "Number of Ask HN posts to return (1-20)"] = 10,
) -> list[Story]:
    """Fetch recent Ask HN posts — questions posed to the Hacker News community."""
    return await _fetch_feed("/askstories.json", max(1, min(count, MAX_SPECIAL_COUNT)))


async def get_show_hn(
    count: Annotated[int, "Number of Show HN posts to return (1-20)"] = 10,
) -> list[Story]:
    """Fetch recent Show HN posts — projects and tools shared by the HN community."""
    return await _fetch_feed("/showstories.json", max(1, min(count, MAX_SPECIAL_COUNT)))
