"""Eval tests — verify Claude selects the correct tool for HN research queries.

These tests make real Anthropic API calls and require ANTHROPIC_API_KEY.

Run with:
    pytest tests/evals/ -m eval -v

Each test asserts that when presented with a natural-language query and the
8 HN Pulse tool schemas, Claude selects the expected tool on the first call.
tool_choice={"type": "any"} forces a tool use response (no free-text hedge).
claude-haiku-4-5 is used for cost efficiency (~$0.002 total for all cases).
"""

import os

import anthropic
import pytest

pytestmark = pytest.mark.eval

TOOL_SCHEMAS = [
    {
        "name": "get_top_stories",
        "description": (
            "Fetch the current top stories from Hacker News, ranked by score and recency."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "description": "Number of stories (1-30)"}},
        },
    },
    {
        "name": "get_new_stories",
        "description": "Fetch the most recently submitted stories from Hacker News.",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer", "description": "Number of stories (1-30)"}},
        },
    },
    {
        "name": "get_story_details",
        "description": (
            "Get full details of a Hacker News story including title, URL, score, and top comments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer", "description": "The numeric HN story ID"},
                "max_comments": {"type": "integer"},
            },
            "required": ["story_id"],
        },
    },
    {
        "name": "search_stories",
        "description": "Search Hacker News stories and comments using Algolia full-text search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "sort_by": {"type": "string", "enum": ["relevance", "date"]},
                "tags": {"type": "string"},
                "num_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_user_profile",
        "description": (
            "Get a Hacker News user's profile: karma, about text, and account creation date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"username": {"type": "string", "description": "HN username"}},
            "required": ["username"],
        },
    },
    {
        "name": "get_job_listings",
        "description": (
            "Fetch current job postings from Hacker News (YC companies and community job posts)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        },
    },
    {
        "name": "get_ask_hn",
        "description": "Fetch recent Ask HN posts — questions posed to the Hacker News community.",
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        },
    },
    {
        "name": "get_show_hn",
        "description": (
            "Fetch recent Show HN posts — projects and tools shared by the HN community."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        },
    },
]

# (query, expected_tool, reason)
CASES = [
    ("What's currently trending on Hacker News?", "get_top_stories", "trending = top stories"),
    ("Show me the hottest stories right now", "get_top_stories", "hot = top stories"),
    ("What are the newest submissions on HN?", "get_new_stories", "newest = new stories"),
    ("Get the most recently posted stories", "get_new_stories", "recent = new stories"),
    ("What are people saying about Rust?", "search_stories", "opinion = search"),
    ("Search for articles about large language models", "search_stories", "explicit search"),
    ("Find current job postings on Hacker News", "get_job_listings", "job = job listings"),
    ("What questions is the HN community asking this week?", "get_ask_hn", "questions = ask hn"),
    ("Show me what people are building and launching on HN", "get_show_hn", "builds = show hn"),
    ("What is user pg's karma and about section?", "get_user_profile", "user lookup"),
]


@pytest.fixture(scope="module")
def anth_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set — skipping eval tests")
    return anthropic.Anthropic(api_key=api_key)


@pytest.mark.parametrize("query,expected_tool,reason", CASES)
def test_tool_selection(query: str, expected_tool: str, reason: str, anth_client):
    """Assert Claude selects the expected tool for a given query."""
    response = anth_client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        tools=TOOL_SCHEMAS,
        tool_choice={"type": "any"},
        messages=[{"role": "user", "content": query}],
    )

    tool_uses = [b for b in response.content if b.type == "tool_use"]
    assert len(tool_uses) >= 1, f"No tool selected for query: '{query}'"

    selected = tool_uses[0].name
    assert selected == expected_tool, (
        f"\nQuery:    '{query}'\n"
        f"Expected: {expected_tool}  ({reason})\n"
        f"Got:      {selected}"
    )
