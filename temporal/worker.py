"""HN Pulse Temporal worker.

Registers all activities and workflows, then starts polling the task queue.

Usage:
    python temporal/worker.py

Environment variables:
    TEMPORAL_HOST       Temporal server gRPC address (default: localhost:7233)
    TEMPORAL_NAMESPACE  Temporal namespace (default: default)
"""

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from temporal.activities import (
    fetch_article,
    get_ask_hn,
    get_new_stories,
    get_show_hn,
    get_story_details,
    get_top_stories,
    get_user_profile,
    search_stories,
)
from temporal.workflows import DailyDigestWorkflow, HNResearchWorkflow, TopicMonitorWorkflow

TASK_QUEUE = "hn-pulse-queue"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    host = os.environ.get("TEMPORAL_HOST", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")

    logger.info("Connecting to Temporal at %s namespace=%s", host, namespace)
    client = await Client.connect(host, namespace=namespace)

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[HNResearchWorkflow, DailyDigestWorkflow, TopicMonitorWorkflow],
        activities=[
            get_top_stories,
            get_new_stories,
            search_stories,
            get_story_details,
            fetch_article,
            get_user_profile,
            get_ask_hn,
            get_show_hn,
        ],
    )

    logger.info("Worker started — task queue: %s", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
