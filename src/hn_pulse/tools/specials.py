"""Job listings, Ask HN, and Show HN feed tools."""

import asyncio
from typing import Annotated

import httpx

from hn_pulse.client import hn_client


async def _fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    try:
        r = await client.get(f"/item/{item_id}.json")
        return r.json() if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


async def _fetch_feed(endpoint: str, count: int) -> list[dict]:
    async with hn_client() as client:
        r = await client.get(endpoint)
        r.raise_for_status()
        ids: list[int] = r.json()[:count]
        items = await asyncio.gather(*[_fetch_item(client, i) for i in ids])
        return [item for item in items if item]


async def get_job_listings(
    count: Annotated[int, "Number of job listings to return (1-20)"] = 10,
) -> list[dict]:
    """Fetch current job postings from Hacker News (YC companies and community job posts)."""
    return await _fetch_feed("/jobstories.json", max(1, min(count, 20)))


async def get_ask_hn(
    count: Annotated[int, "Number of Ask HN posts to return (1-20)"] = 10,
) -> list[dict]:
    """Fetch recent Ask HN posts — questions posed to the Hacker News community."""
    return await _fetch_feed("/askstories.json", max(1, min(count, 20)))


async def get_show_hn(
    count: Annotated[int, "Number of Show HN posts to return (1-20)"] = 10,
) -> list[dict]:
    """Fetch recent Show HN posts — projects and tools shared by the HN community."""
    return await _fetch_feed("/showstories.json", max(1, min(count, 20)))
