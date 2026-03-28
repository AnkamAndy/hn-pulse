#!/usr/bin/env python3
"""HN Pulse MCP Server — exposes Hacker News data via the Model Context Protocol."""

import argparse

from arcade_mcp_server import MCPApp

from hn_pulse.tools import ALL_TOOLS

app = MCPApp(
    name="hn_pulse",
    version="1.0.0",
    instructions=(
        "Provides tools to read Hacker News stories, search discussions, look up user "
        "profiles, and fetch job postings — all via the public HN and Algolia APIs."
    ),
    log_level="INFO",
)

for _tool in ALL_TOOLS:
    app.add_tool(_tool)  # type: ignore[arg-type]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HN Pulse MCP Server")
    parser.add_argument(
        "transport",
        nargs="?",
        default="stdio",
        choices=["stdio", "http"],
        help="Transport type (default: stdio)",
    )
    parser.add_argument("--transport", dest="transport_flag", choices=["stdio", "http"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    transport = args.transport_flag or args.transport
    app.run(transport=transport, host=args.host, port=args.port)
