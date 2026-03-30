"""HN Pulse Temporal workflow definitions.

Three workflows:
  HNResearchWorkflow   — on-demand: search → fan-out details → optional article fetch
  DailyDigestWorkflow  — scheduled: top/ask/show feeds → details for top 3 → markdown file
  TopicMonitorWorkflow — long-running: periodic search with durable sleep, accumulates new hits
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities import (
        fetch_article,
        get_ask_hn,
        get_show_hn,
        get_story_details,
        get_top_stories,
        search_stories,
    )

# ── Shared retry policy ────────────────────────────────────────────────────

_RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    non_retryable_error_types=["temporalio.exceptions.ApplicationError"],
)

_ITEM_TIMEOUT = timedelta(seconds=30)
_ARTICLE_TIMEOUT = timedelta(seconds=45)
_SEARCH_TIMEOUT = timedelta(seconds=30)
_FEED_TIMEOUT = timedelta(seconds=30)


# ── Input dataclasses ──────────────────────────────────────────────────────


@dataclass
class ResearchInput:
    query: str
    tags: str = "story"
    num_results: int = 10
    fetch_articles: bool = False


@dataclass
class DigestInput:
    top_count: int = 10
    ask_count: int = 5
    show_count: int = 5
    detail_count: int = 3
    output_dir: str = "output"


@dataclass
class MonitorInput:
    topic: str
    check_interval_hours: int = 6
    max_iterations: int = 28  # 7 days at 6-hour intervals


# ── HNResearchWorkflow ─────────────────────────────────────────────────────


@workflow.defn
class HNResearchWorkflow:
    """On-demand: search HN → fan-out story details → optionally fetch articles."""

    @workflow.run
    async def run(self, input: ResearchInput) -> dict[str, Any]:
        if not workflow.unsafe.is_replaying():
            workflow.logger.info(
                "HNResearchWorkflow query=%r tags=%s fetch_articles=%s",
                input.query,
                input.tags,
                input.fetch_articles,
            )

        # Step 1: search Algolia
        search_result: dict = await workflow.execute_activity(
            search_stories,
            args=[input.query, "relevance", input.tags, input.num_results, 0],
            schedule_to_close_timeout=_SEARCH_TIMEOUT,
            retry_policy=_RETRY,
        )
        hits: list[dict] = search_result.get("hits", [])

        # Step 2: fan-out get_story_details for each hit
        story_ids = [int(h["story_id"]) for h in hits if h.get("story_id")]
        details: list[dict] = list(
            await asyncio.gather(
                *[
                    workflow.execute_activity(
                        get_story_details,
                        args=[sid, 5, False],
                        schedule_to_close_timeout=_ITEM_TIMEOUT,
                        retry_policy=_RETRY,
                    )
                    for sid in story_ids
                ]
            )
        )

        # Step 3: optionally fetch article body (best-effort — failures don't fail workflow)
        articles: list[dict] = []
        if input.fetch_articles:
            urls = [d.get("url") for d in details if d.get("url")]
            raw = await asyncio.gather(
                *[
                    workflow.execute_activity(
                        fetch_article,
                        args=[url, 3000],
                        schedule_to_close_timeout=_ARTICLE_TIMEOUT,
                        retry_policy=_RETRY,
                    )
                    for url in urls
                ],
                return_exceptions=True,
            )
            articles = [a for a in raw if isinstance(a, dict)]

        return {
            "query": input.query,
            "total_hits": search_result.get("total_hits", 0),
            "stories_fetched": len(details),
            "articles_fetched": len(articles),
            "stories": details,
            "articles": articles,
            "workflow_id": workflow.info().workflow_id,
            "run_id": workflow.info().run_id,
        }


# ── DailyDigestWorkflow ────────────────────────────────────────────────────


@workflow.defn
class DailyDigestWorkflow:
    """Scheduled: fetch top/ask/show concurrently, detail top 3, write digest."""

    @workflow.run
    async def run(self, input: DigestInput) -> dict[str, Any]:
        if not workflow.unsafe.is_replaying():
            workflow.logger.info("DailyDigestWorkflow started")

        # Step 1: fan-out three feeds concurrently
        top_stories, ask_stories, show_stories = await asyncio.gather(
            workflow.execute_activity(
                get_top_stories,
                args=[input.top_count],
                schedule_to_close_timeout=_FEED_TIMEOUT,
                retry_policy=_RETRY,
            ),
            workflow.execute_activity(
                get_ask_hn,
                args=[input.ask_count],
                schedule_to_close_timeout=_FEED_TIMEOUT,
                retry_policy=_RETRY,
            ),
            workflow.execute_activity(
                get_show_hn,
                args=[input.show_count],
                schedule_to_close_timeout=_FEED_TIMEOUT,
                retry_policy=_RETRY,
            ),
        )

        # Step 2: get story details for top N stories
        detail_ids = [s["id"] for s in top_stories[: input.detail_count] if s.get("id")]
        detailed: list[dict] = list(
            await asyncio.gather(
                *[
                    workflow.execute_activity(
                        get_story_details,
                        args=[sid, 5, False],
                        schedule_to_close_timeout=_ITEM_TIMEOUT,
                        retry_policy=_RETRY,
                    )
                    for sid in detail_ids
                ]
            )
        )

        # Step 3: build and write digest (file write gated outside replay)
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        digest_md = _build_digest_markdown(
            date_str, top_stories, ask_stories, show_stories, detailed
        )

        output_path: str | None = None
        if not workflow.unsafe.is_replaying():
            output_path = _write_digest(input.output_dir, date_str, digest_md)
            workflow.logger.info("Digest written to %s", output_path)

        return {
            "date": date_str,
            "output_path": output_path,
            "top_count": len(top_stories),
            "ask_count": len(ask_stories),
            "show_count": len(show_stories),
            "digest_preview": digest_md[:500],
        }


def _build_digest_markdown(
    date_str: str,
    top_stories: list[dict],
    ask_stories: list[dict],
    show_stories: list[dict],
    detailed: list[dict],
) -> str:
    lines: list[str] = [
        f"# HN Daily Digest — {date_str}",
        f"_Generated at {datetime.now(UTC).strftime('%H:%M UTC')}_",
        "",
        "## Top Stories",
    ]
    for i, s in enumerate(top_stories, 1):
        url = s.get("url") or f"https://news.ycombinator.com/item?id={s.get('id')}"
        lines.append(
            f"{i}. [{s.get('title', '(no title)')}]({url})"
            f" — {s.get('score', 0)} pts · {s.get('descendants', 0)} comments"
        )

    if detailed:
        lines += ["", "### Story Highlights"]
        for d in detailed:
            lines.append(f"\n**{d.get('title', '(no title)')}** by {d.get('by', 'unknown')}")
            for c in (d.get("comments") or [])[:2]:
                text = str(c.get("text", ""))[:200]
                lines.append(f"> {text}")

    lines += ["", "## Ask HN"]
    for s in ask_stories:
        lines.append(f"- [{s.get('title', '?')}](https://news.ycombinator.com/item?id={s.get('id')})")

    lines += ["", "## Show HN"]
    for s in show_stories:
        lines.append(f"- [{s.get('title', '?')}](https://news.ycombinator.com/item?id={s.get('id')})")

    return "\n".join(lines)


def _write_digest(output_dir: str, date_str: str, content: str) -> str:
    path = Path(output_dir) / f"digest-{date_str}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


# ── TopicMonitorWorkflow ───────────────────────────────────────────────────


@workflow.defn
class TopicMonitorWorkflow:
    """Long-running: periodically search a topic and accumulate new story hits."""

    @workflow.run
    async def run(self, input: MonitorInput) -> dict[str, Any]:
        if not workflow.unsafe.is_replaying():
            workflow.logger.info(
                "TopicMonitorWorkflow topic=%r interval=%dh max_iter=%d",
                input.topic,
                input.check_interval_hours,
                input.max_iterations,
            )

        seen_ids: set[str] = set()
        all_new_hits: list[dict] = []
        sleep_duration = timedelta(hours=input.check_interval_hours)

        for iteration in range(1, input.max_iterations + 1):
            if not workflow.unsafe.is_replaying():
                workflow.logger.info(
                    "TopicMonitor iter %d/%d topic=%r",
                    iteration,
                    input.max_iterations,
                    input.topic,
                )

            result: dict = await workflow.execute_activity(
                search_stories,
                args=[input.topic, "date", "story", 20, 0],
                schedule_to_close_timeout=_SEARCH_TIMEOUT,
                retry_policy=_RETRY,
            )

            new_hits = [
                h for h in result.get("hits", []) if str(h.get("story_id", "")) not in seen_ids
            ]
            for h in new_hits:
                if h.get("story_id"):
                    seen_ids.add(str(h["story_id"]))
            all_new_hits.extend(new_hits)

            if not workflow.unsafe.is_replaying():
                workflow.logger.info(
                    "TopicMonitor: %d new hits this iter, %d total",
                    len(new_hits),
                    len(all_new_hits),
                )

            if iteration < input.max_iterations:
                await workflow.sleep(sleep_duration)

        return {
            "topic": input.topic,
            "iterations": input.max_iterations,
            "total_new_stories": len(all_new_hits),
            "stories": all_new_hits,
        }
