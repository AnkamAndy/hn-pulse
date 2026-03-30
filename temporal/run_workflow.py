"""CLI to trigger HN Pulse Temporal workflows.

Usage:
    python temporal/run_workflow.py research "what are people saying about Rust?"
    python temporal/run_workflow.py research "AI agents" --fetch-articles
    python temporal/run_workflow.py digest
    python temporal/run_workflow.py digest --top 15 --output output/
    python temporal/run_workflow.py monitor "LLM" --interval 6 --days 7

Environment variables:
    TEMPORAL_HOST       (default: localhost:7233)
    TEMPORAL_NAMESPACE  (default: default)
"""

import asyncio
import json
import os
import sys
import uuid
from argparse import ArgumentParser
from datetime import timedelta

from temporalio.client import Client

from temporal.workflows import (
    DailyDigestWorkflow,
    DigestInput,
    HNResearchWorkflow,
    MonitorInput,
    ResearchInput,
    TopicMonitorWorkflow,
)

TASK_QUEUE = "hn-pulse-queue"


async def _connect() -> Client:
    host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    return await Client.connect(host, namespace=namespace)


async def run_research(args: object) -> None:
    client = await _connect()
    workflow_id = f"research-{uuid.uuid4().hex[:8]}"
    input = ResearchInput(
        query=args.query,  # type: ignore[attr-defined]
        tags=args.tags,  # type: ignore[attr-defined]
        num_results=args.num_results,  # type: ignore[attr-defined]
        fetch_articles=args.fetch_articles,  # type: ignore[attr-defined]
    )
    print(f"Starting HNResearchWorkflow id={workflow_id} query={input.query!r}")
    result = await client.execute_workflow(
        HNResearchWorkflow.run,
        input,
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(minutes=10),
    )
    print(json.dumps(result, indent=2, default=str))


async def run_digest(args: object) -> None:
    client = await _connect()
    workflow_id = f"digest-{uuid.uuid4().hex[:8]}"
    input = DigestInput(
        top_count=args.top,  # type: ignore[attr-defined]
        ask_count=args.ask,  # type: ignore[attr-defined]
        show_count=args.show,  # type: ignore[attr-defined]
        detail_count=args.detail,  # type: ignore[attr-defined]
        output_dir=args.output,  # type: ignore[attr-defined]
    )
    print(f"Starting DailyDigestWorkflow id={workflow_id}")
    result = await client.execute_workflow(
        DailyDigestWorkflow.run,
        input,
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(minutes=5),
    )
    print(json.dumps(result, indent=2, default=str))
    if result.get("output_path"):
        print(f"\nDigest written to: {result['output_path']}")


async def run_monitor(args: object) -> None:
    client = await _connect()
    topic: str = args.topic  # type: ignore[attr-defined]
    interval: int = args.interval  # type: ignore[attr-defined]
    days: int = args.days  # type: ignore[attr-defined]
    topic_slug = topic.lower().replace(" ", "-")
    workflow_id = f"monitor-{topic_slug}-{uuid.uuid4().hex[:8]}"
    max_iterations = (days * 24) // interval
    input = MonitorInput(topic=topic, check_interval_hours=interval, max_iterations=max_iterations)
    print(
        f"Starting TopicMonitorWorkflow id={workflow_id} "
        f"topic={topic!r} interval={interval}h iterations={max_iterations} (~{days} days)"
    )
    handle = await client.start_workflow(
        TopicMonitorWorkflow.run,
        input,
        id=workflow_id,
        task_queue=TASK_QUEUE,
        execution_timeout=timedelta(hours=days * 24 + 2),
    )
    print("Monitor started — check progress in the Temporal UI:")
    print(f"  Workflow ID : {handle.id}")
    print(f"  UI          : http://localhost:8233/namespaces/default/workflows/{handle.id}")


def _build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="HN Pulse Temporal workflow runner")
    sub = parser.add_subparsers(dest="command", required=True)

    p_research = sub.add_parser("research", help="On-demand research workflow")
    p_research.add_argument("query", help="Research query string")
    p_research.add_argument("--tags", default="story")
    p_research.add_argument("--num-results", type=int, default=10, dest="num_results")
    p_research.add_argument("--fetch-articles", action="store_true", dest="fetch_articles")

    p_digest = sub.add_parser("digest", help="Daily digest workflow")
    p_digest.add_argument("--top", type=int, default=10)
    p_digest.add_argument("--ask", type=int, default=5)
    p_digest.add_argument("--show", type=int, default=5)
    p_digest.add_argument("--detail", type=int, default=3)
    p_digest.add_argument("--output", default="output")

    p_monitor = sub.add_parser("monitor", help="Long-running topic monitor workflow")
    p_monitor.add_argument("topic", help="Topic to monitor")
    p_monitor.add_argument("--interval", type=int, default=6, help="Check interval in hours")
    p_monitor.add_argument("--days", type=int, default=7, help="Total monitoring duration in days")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    match args.command:
        case "research":
            asyncio.run(run_research(args))
        case "digest":
            asyncio.run(run_digest(args))
        case "monitor":
            asyncio.run(run_monitor(args))
        case _:
            parser.print_help()
            sys.exit(1)


if __name__ == "__main__":
    main()
