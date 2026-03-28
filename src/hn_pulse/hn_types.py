"""TypedDict definitions for all HN Pulse tool return shapes."""

from typing import TypedDict


class Story(TypedDict, total=False):
    id: int
    type: str
    title: str
    url: str
    by: str
    score: int
    time: int
    descendants: int
    comments: list[dict]


class Comment(TypedDict, total=False):
    id: int
    type: str
    by: str
    text: str
    time: int
    parent: int
    replies: list[dict]


class UserProfile(TypedDict, total=False):
    id: str
    karma: int
    created: int
    about: str
    recent_submissions: list[int]


class SearchHit(TypedDict, total=False):
    story_id: str
    title: str | None
    url: str | None
    author: str | None
    points: int | None
    num_comments: int | None
    created_at: str | None
    text: str | None


class SearchResponse(TypedDict):
    query: str
    total_hits: int
    page: int
    total_pages: int
    hits: list[SearchHit]
