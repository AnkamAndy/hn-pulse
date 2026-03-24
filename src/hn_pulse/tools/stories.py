"""Top and new story feed tools."""

import asyncio
from typing import Annotated

import httpx

from hn_pulse.client import hn_client


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    """Fetch a single HN item by ID; returns None on error or missing item."""
    try:
        r = await client.get(f"/item/{item_id}.json")
        if r.status_code == 200:
            return r.json()
    except httpx.HTTPError:
        pass
    return None


async def get_top_stories(
    count: Annotated[int, "Number of top stories to return (1-30)"] = 10,
) -> list[dict]:
    """Fetch the current top stories from Hacker News, ranked by score and recency."""
    count = max(1, min(count, 30))
    async with hn_client() as client:
        r = await client.get("/topstories.json")
        r.raise_for_status()
        ids: list[int] = r.json()[:count]
        stories = await asyncio.gather(*[_fetch_item(client, i) for i in ids])
        return [s for s in stories if s]


async def get_new_stories(
    count: Annotated[int, "Number of new stories to return (1-30)"] = 10,
) -> list[dict]:
    """Fetch the most recently submitted stories from Hacker News."""
    count = max(1, min(count, 30))
    async with hn_client() as client:
        r = await client.get("/newstories.json")
        r.raise_for_status()
        ids: list[int] = r.json()[:count]
        stories = await asyncio.gather(*[_fetch_item(client, i) for i in ids])
        return [s for s in stories if s]
