"""Shared helpers, constants, and concurrency utilities for all HN Pulse tools."""

import asyncio
import logging
from collections.abc import Awaitable

import httpx
from httpx import DecodingError

logger = logging.getLogger(__name__)

# ── Item count limits ────────────────────────────────────────────────
MAX_STORY_COUNT: int = 30
MAX_SPECIAL_COUNT: int = 20
MAX_COMMENTS: int = 20
MAX_REPLY_CHILDREN: int = 5
MAX_USER_SUBMISSIONS: int = 10


async def fetch_item(client: httpx.AsyncClient, item_id: int) -> dict | None:
    """Fetch a single HN item; returns None on error or null response. Logs failures."""
    try:
        r = await client.get(f"/item/{item_id}.json")
        if r.status_code != 200:
            logger.warning("item %d: HTTP %d", item_id, r.status_code)
            return None
        data: dict | None = r.json()
        if data is None:
            logger.debug("item %d: null (deleted or missing)", item_id)
        return data
    except (httpx.HTTPError, DecodingError, ValueError) as exc:
        logger.warning("item %d: network error — %s", item_id, exc)
        return None


async def gather_items(
    coros: list[Awaitable[dict | None]],
    label: str,
) -> list[dict]:
    """Run coroutines concurrently; log failure rate; return only non-None results."""
    results = await asyncio.gather(*coros)
    total = len(results)
    failed = sum(1 for r in results if r is None)
    if failed:
        logger.info("gather[%s]: %d/%d items unavailable", label, failed, total)
    return [r for r in results if r is not None]
