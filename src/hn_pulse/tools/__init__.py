"""Tool registry — exports ALL_TOOLS for registration in server.py."""

from hn_pulse.tools.item import get_story_details
from hn_pulse.tools.search import search_stories
from hn_pulse.tools.specials import get_ask_hn, get_job_listings, get_show_hn
from hn_pulse.tools.stories import get_new_stories, get_top_stories
from hn_pulse.tools.users import get_user_profile

ALL_TOOLS = [
    get_top_stories,
    get_new_stories,
    get_story_details,
    search_stories,
    get_user_profile,
    get_job_listings,
    get_ask_hn,
    get_show_hn,
]

__all__ = ["ALL_TOOLS"]
