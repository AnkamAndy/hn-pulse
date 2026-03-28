#!/usr/bin/env python3
"""HN Fetch MCP Server — article URL fetcher for HN Pulse multi-service setup.

Exposes one tool:
    HnFetch_FetchArticle(url, max_chars) → {url, status_code, body, ...}

Run standalone:
    uv run src/hn_extras/server.py          # stdio (default)
    uv run src/hn_extras/server.py http --host 0.0.0.0 --port 8001

In docker-compose this runs as the 'fetch-server' service alongside hn-server.
The agent enables it via ENABLE_FETCH=1 (local) or HN_FETCH_URL=http://...
"""

import argparse

from hn_extras.fetch import app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HN Fetch MCP Server")
    parser.add_argument(
        "transport",
        nargs="?",
        default="stdio",
        choices=["stdio", "http"],
    )
    parser.add_argument("--transport", dest="transport_flag", choices=["stdio", "http"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    transport = args.transport_flag or args.transport
    app.run(transport=transport, host=args.host, port=args.port)
