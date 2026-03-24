"""User profile lookup tool."""

from typing import Annotated

from hn_pulse.client import hn_client


async def get_user_profile(
    username: Annotated[str, "Hacker News username (case-sensitive)"],
    include_recent_submissions: Annotated[
        bool, "Whether to include the last 10 submission IDs"
    ] = False,
) -> dict:
    """Get a Hacker News user's profile: karma, about text, and account creation date."""
    async with hn_client() as client:
        r = await client.get(f"/user/{username}.json")
        r.raise_for_status()
        user = r.json()
        if not user:
            return {"error": f"User '{username}' not found"}

        result: dict = {
            "id": user["id"],
            "karma": user.get("karma", 0),
            "created": user.get("created"),
            "about": user.get("about", ""),
        }
        if include_recent_submissions:
            result["recent_submissions"] = user.get("submitted", [])[:10]
        return result
