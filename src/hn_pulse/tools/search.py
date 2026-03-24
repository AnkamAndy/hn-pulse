"""Algolia full-text search tool for Hacker News."""

from typing import Annotated, Literal

from hn_pulse.client import algolia_client


def _clean_hit(hit: dict) -> dict:
    """Strip Algolia metadata, keeping only fields useful to an LLM."""
    return {
        "story_id": hit.get("story_id") or hit.get("objectID"),
        "title": hit.get("title") or hit.get("story_title"),
        "url": hit.get("url") or hit.get("story_url"),
        "author": hit.get("author"),
        "points": hit.get("points"),
        "num_comments": hit.get("num_comments"),
        "created_at": hit.get("created_at"),
        "text": hit.get("story_text") or hit.get("comment_text"),
    }


async def search_stories(
    query: Annotated[str, "Search query string"],
    sort_by: Annotated[
        Literal["relevance", "date"],
        "Sort results by relevance (default) or recency",
    ] = "relevance",
    tags: Annotated[
        str,
        "Filter by HN tag: story, comment, ask_hn, show_hn, or job (default: story)",
    ] = "story",
    num_results: Annotated[int, "Number of results to return (1-20)"] = 10,
    page: Annotated[int, "Page number for pagination (0-indexed)"] = 0,
) -> dict:
    """Search Hacker News stories and comments using Algolia full-text search."""
    num_results = max(1, min(num_results, 20))
    endpoint = "/search" if sort_by == "relevance" else "/search_by_date"

    async with algolia_client() as client:
        r = await client.get(
            endpoint,
            params={
                "query": query,
                "tags": tags,
                "hitsPerPage": num_results,
                "page": page,
            },
        )
        r.raise_for_status()
        data = r.json()
        return {
            "query": data["query"],
            "total_hits": data["nbHits"],
            "page": data["page"],
            "total_pages": data["nbPages"],
            "hits": [_clean_hit(h) for h in data["hits"]],
        }
