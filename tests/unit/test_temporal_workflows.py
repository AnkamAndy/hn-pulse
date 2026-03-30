"""Unit tests for Temporal workflow orchestration logic.

Uses WorkflowEnvironment.start_time_skipping() — no live Temporal server needed.
workflow.sleep() calls advance instantly. Activities are replaced with lightweight
mocks that return canned data so we can assert on workflow control flow.
"""

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import (
    DailyDigestWorkflow,
    DigestInput,
    HNResearchWorkflow,
    MonitorInput,
    ResearchInput,
    TopicMonitorWorkflow,
)

TASK_QUEUE = "test-hn-pulse"


# ── Mock activities ───────────────────────────────────────────────────────────
# Registered under the same names as the real activities so Temporal routes to them.


@activity.defn(name="search_stories")
async def mock_search_stories(
    query: str, sort_by: str, tags: str, num_results: int, page: int
) -> dict:
    return {
        "query": query,
        "total_hits": 2,
        "hits": [
            {"story_id": "12345", "title": "Rust 2025", "url": "https://example.com/1"},
            {"story_id": "67890", "title": "Rust vs Go", "url": "https://example.com/2"},
        ],
    }


@activity.defn(name="get_story_details")
async def mock_get_story_details(
    story_id: int, max_comments: int, include_replies: bool
) -> dict:
    return {
        "id": story_id,
        "title": f"Story {story_id}",
        "by": "author",
        "url": f"https://example.com/{story_id}",
        "score": 100,
        "descendants": 20,
        "comments": [{"text": "Great post!", "by": "commenter"}],
    }


@activity.defn(name="get_top_stories")
async def mock_get_top_stories(count: int) -> list[dict]:
    return [
        {"id": i, "title": f"Top Story {i}", "score": 100 + i, "descendants": i * 2}
        for i in range(1, count + 1)
    ]


@activity.defn(name="get_ask_hn")
async def mock_get_ask_hn(count: int) -> list[dict]:
    return [{"id": 200 + i, "title": f"Ask HN: Question {i}"} for i in range(count)]


@activity.defn(name="get_show_hn")
async def mock_get_show_hn(count: int) -> list[dict]:
    return [{"id": 300 + i, "title": f"Show HN: Project {i}"} for i in range(count)]


@activity.defn(name="fetch_article")
async def mock_fetch_article(url: str, max_chars: int) -> dict:
    return {"url": url, "content": "Article body text."}


_ALL_MOCK_ACTIVITIES = [
    mock_search_stories,
    mock_get_story_details,
    mock_get_top_stories,
    mock_get_ask_hn,
    mock_get_show_hn,
    mock_fetch_article,
]


# ── HNResearchWorkflow ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_research_workflow_returns_stories():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HNResearchWorkflow],
            activities=_ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                HNResearchWorkflow.run,
                ResearchInput(query="rust", num_results=2),
                id="test-research-1",
                task_queue=TASK_QUEUE,
            )

    assert result["query"] == "rust"
    assert result["stories_fetched"] == 2
    assert result["articles_fetched"] == 0
    assert len(result["stories"]) == 2
    assert result["stories"][0]["id"] == 12345


@pytest.mark.asyncio
async def test_research_workflow_fetches_articles_when_requested():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HNResearchWorkflow],
            activities=_ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                HNResearchWorkflow.run,
                ResearchInput(query="rust", num_results=2, fetch_articles=True),
                id="test-research-2",
                task_queue=TASK_QUEUE,
            )

    assert result["articles_fetched"] == 2
    assert len(result["articles"]) == 2


@pytest.mark.asyncio
async def test_research_workflow_returns_empty_on_no_hits():
    """When search returns no story_id fields, details step is skipped."""

    @activity.defn(name="search_stories")
    async def empty_search(
        query: str, sort_by: str, tags: str, num_results: int, page: int
    ) -> dict:
        return {"query": query, "total_hits": 0, "hits": []}

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[HNResearchWorkflow],
            activities=[empty_search, *_ALL_MOCK_ACTIVITIES[1:]],
        ):
            result = await env.client.execute_workflow(
                HNResearchWorkflow.run,
                ResearchInput(query="obscure topic"),
                id="test-research-3",
                task_queue=TASK_QUEUE,
            )

    assert result["stories_fetched"] == 0
    assert result["articles_fetched"] == 0


# ── DailyDigestWorkflow ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_digest_workflow_returns_expected_counts(tmp_path):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[DailyDigestWorkflow],
            activities=_ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                DailyDigestWorkflow.run,
                DigestInput(
                    top_count=5,
                    ask_count=3,
                    show_count=3,
                    detail_count=2,
                    output_dir=str(tmp_path),
                ),
                id="test-digest-1",
                task_queue=TASK_QUEUE,
            )

    assert result["top_count"] == 5
    assert result["ask_count"] == 3
    assert result["show_count"] == 3
    assert "date" in result
    assert "digest_preview" in result


@pytest.mark.asyncio
async def test_digest_workflow_preview_contains_section_headers(tmp_path):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[DailyDigestWorkflow],
            activities=_ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                DailyDigestWorkflow.run,
                DigestInput(output_dir=str(tmp_path)),
                id="test-digest-2",
                task_queue=TASK_QUEUE,
            )

    preview = result["digest_preview"]
    assert "# HN Daily Digest" in preview
    assert "## Top Stories" in preview


# ── TopicMonitorWorkflow ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_monitor_workflow_accumulates_new_hits():
    """2 iterations: first sees 2 hits, second sees same 2 (already in seen_ids)."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[TopicMonitorWorkflow],
            activities=_ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                TopicMonitorWorkflow.run,
                MonitorInput(topic="rust", check_interval_hours=1, max_iterations=2),
                id="test-monitor-1",
                task_queue=TASK_QUEUE,
            )

    assert result["topic"] == "rust"
    assert result["iterations"] == 2
    # First iteration: 2 new hits. Second iteration: same IDs already seen → 0 new.
    assert result["total_new_stories"] == 2


@pytest.mark.asyncio
async def test_monitor_workflow_deduplicates_seen_stories():
    """Verify seen_ids prevents counting the same story twice."""
    call_count = 0

    @activity.defn(name="search_stories")
    async def two_phase_search(
        query: str, sort_by: str, tags: str, num_results: int, page: int
    ) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "query": query,
                "total_hits": 1,
                "hits": [{"story_id": "111", "title": "New story"}],
            }
        # Second call returns a mix: one already seen + one truly new
        return {
            "query": query,
            "total_hits": 2,
            "hits": [
                {"story_id": "111", "title": "New story"},  # already seen
                {"story_id": "222", "title": "Another story"},  # new
            ],
        }

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[TopicMonitorWorkflow],
            activities=[two_phase_search, *_ALL_MOCK_ACTIVITIES[1:]],
        ):
            result = await env.client.execute_workflow(
                TopicMonitorWorkflow.run,
                MonitorInput(topic="dedup-test", check_interval_hours=1, max_iterations=2),
                id="test-monitor-2",
                task_queue=TASK_QUEUE,
            )

    # 1 from iter 1 + 1 genuinely new from iter 2 = 2 total
    assert result["total_new_stories"] == 2
    story_ids = {str(s["story_id"]) for s in result["stories"]}
    assert story_ids == {"111", "222"}
