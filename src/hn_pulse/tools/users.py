"""User profile lookup tool."""

import logging
from typing import Annotated

from hn_pulse.client import hn_client
from hn_pulse.tools.common import MAX_USER_SUBMISSIONS
from hn_pulse.types import UserProfile

logger = logging.getLogger(__name__)


async def get_user_profile(
    username: Annotated[str, "Hacker News username (case-sensitive)"],
    include_recent_submissions: Annotated[
        bool, "Whether to include the last 10 submission IDs"
    ] = False,
) -> UserProfile:
    """Get a Hacker News user's profile: karma, about text, and account creation date."""
    async with hn_client() as client:
        r = await client.get(f"/user/{username}.json")
        r.raise_for_status()
        user = r.json()
        if not user:
            return {"error": f"User '{username}' not found"}  # type: ignore[return-value,typeddict-unknown-key]

        logger.debug("user '%s': karma=%d", username, user.get("karma", 0))
        result: UserProfile = {
            "id": user["id"],
            "karma": user.get("karma", 0),
            "created": user.get("created"),
            "about": user.get("about", ""),
        }
        if include_recent_submissions:
            result["recent_submissions"] = user.get("submitted", [])[:MAX_USER_SUBMISSIONS]
        return result
