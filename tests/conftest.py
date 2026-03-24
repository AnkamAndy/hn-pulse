"""Shared test fixtures and mock data for HN Pulse tests."""

MOCK_STORY = {
    "id": 12345,
    "type": "story",
    "title": "Announcing Rust 2025 Edition",
    "url": "https://blog.rust-lang.org/2025/rust-edition",
    "by": "rustlang",
    "score": 850,
    "time": 1700000000,
    "descendants": 42,
    "kids": [99001, 99002, 99003],
}

MOCK_COMMENT = {
    "id": 99001,
    "type": "comment",
    "by": "hacker1",
    "text": "This is a great announcement!",
    "time": 1700000100,
    "parent": 12345,
}

MOCK_DELETED_COMMENT = {
    "id": 99002,
    "deleted": True,
}

MOCK_DEAD_COMMENT = {
    "id": 99003,
    "dead": True,
    "by": "spammer",
    "text": "Buy crypto now",
}

MOCK_USER = {
    "id": "rustlang",
    "karma": 9999,
    "created": 1400000000,
    "about": "Official Rust Language account",
    "submitted": list(range(12345, 12356)),
}

MOCK_ALGOLIA_RESPONSE = {
    "query": "rust",
    "nbHits": 5000,
    "nbPages": 250,
    "page": 0,
    "hitsPerPage": 2,
    "hits": [
        {
            "objectID": "12345",
            "story_id": "12345",
            "title": "Rust 2025 Edition",
            "url": "https://blog.rust-lang.org/2025",
            "author": "rustlang",
            "points": 850,
            "num_comments": 200,
            "created_at": "2025-01-01T00:00:00Z",
            "_highlightResult": {"title": {"value": "<em>Rust</em> 2025"}},
            "_tags": ["story", "author_rustlang"],
            "children": [99001, 99002],
            "updated_at": "2025-01-02T00:00:00Z",
        },
        {
            "objectID": "67890",
            "story_id": "67890",
            "title": "Rust vs Go in 2025",
            "url": "https://example.com/rust-vs-go",
            "author": "devblogger",
            "points": 300,
            "num_comments": 80,
            "created_at": "2025-01-05T00:00:00Z",
            "_highlightResult": {},
            "_tags": ["story"],
            "children": [],
        },
    ],
}

MOCK_JOB = {
    "id": 55555,
    "type": "job",
    "title": "Senior Rust Engineer at YC Startup",
    "url": "https://ycstartup.com/jobs",
    "by": "ycstartup",
    "time": 1700000500,
    "score": 1,
}
