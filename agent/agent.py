#!/usr/bin/env python3
"""HN Research Agent — LangGraph-powered CLI for querying Hacker News via MCP.

Supports two transport modes, selected by environment variable:

  Local (default — server spawned as a subprocess via stdio):
      python agent/agent.py "What's trending on HN?"

  Remote (server already running on another machine via HTTP):
      MCP_SERVER_URL=http://192.168.1.10:8000/mcp/ python agent/agent.py "..."

  Start the remote server with:
      uv run src/hn_pulse/server.py http --host 0.0.0.0 --port 8000

Uses MultiServerMCPClient from langchain-mcp-adapters so that local/remote
transports are handled identically — no code changes needed to switch modes.

Usage:
    python agent/agent.py                           # interactive mode
    python agent/agent.py "What's trending on HN?"  # one-shot mode
"""

import asyncio
import os
import sys
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt.chat_agent_executor import create_react_agent
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

SERVER_SCRIPT = str(Path(__file__).parent.parent / "src" / "hn_pulse" / "server.py")

SYSTEM_PROMPT = """\
You are an expert Hacker News research assistant with access to the HN API and Algolia search.

Use the available tools to answer questions about Hacker News stories, discussions, users,
job listings, Ask HN posts, and Show HN projects.

Always synthesize results into a clear, structured answer.
Cite story titles, authors, and scores when referencing specific content.
"""

console = Console()


def _connection_config() -> dict:
    """Return MultiServerMCPClient connection config.

    If MCP_SERVER_URL is set, connect to a remote HTTP server.
    Otherwise, spawn the server locally via stdio.
    """
    server_url = os.environ.get("MCP_SERVER_URL")
    if server_url:
        return {
            "hn_pulse": {
                "transport": "streamable_http",
                "url": server_url,
            }
        }
    # Local stdio: spawns the server as a subprocess on this machine
    return {
        "hn_pulse": {
            "transport": "stdio",
            "command": sys.executable,
            "args": [SERVER_SCRIPT, "stdio"],
        }
    }


async def run_query(query: str, agent) -> None:  # type: ignore[type-arg]
    """Invoke the agent with a single query and print tool calls + final answer."""
    console.print(f"\n[bold yellow]Query:[/bold yellow] {query}\n")

    result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

    # Show tool calls from intermediate messages
    for msg in result.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                args_str = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
                preview = args_str[:80] + "…" if len(args_str) > 80 else args_str
                console.print(f"[dim]  → calling [cyan]{name}[/cyan]({preview})[/dim]")

    # Extract final answer from the last AIMessage
    messages = result.get("messages", [])
    if not messages:
        console.print("[red]No response received.[/red]")
        return

    content = messages[-1].content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b) for b in content
        )
    else:
        text = str(content)

    console.print(Markdown(text))


async def main() -> None:
    config = _connection_config()
    server_url = os.environ.get("MCP_SERVER_URL")
    transport_label = f"HTTP → {server_url}" if server_url else "stdio (local subprocess)"

    # MultiServerMCPClient is not a context manager in 0.2.x — instantiate directly.
    # The tools it returns carry an internal reference to the live connection.
    client = MultiServerMCPClient(config)
    tools = await client.get_tools()
    tool_names = [t.name for t in tools]

    console.print(
        Panel(
            f"[bold green]HN Pulse Research Agent[/bold green] "
            f"[dim](LangGraph · {transport_label})[/dim]\n"
            f"[dim]{len(tool_names)} tools:[/dim] "
            + "  ".join(f"[cyan]{n}[/cyan]" for n in tool_names),
            expand=False,
        )
    )

    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=4096)
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    if len(sys.argv) > 1:
        # One-shot mode: query from CLI args
        query = " ".join(sys.argv[1:])
        await run_query(query, agent)
    else:
        # Interactive mode
        console.print("[dim]Type your question or 'quit' to exit.[/dim]\n")
        while True:
            try:
                query = Prompt.ask("[bold]>[/bold]").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not query or query.lower() in ("quit", "exit", "q"):
                break
            await run_query(query, agent)
            console.print()


if __name__ == "__main__":
    asyncio.run(main())
