#!/usr/bin/env python3
"""HN Research Agent — stateful LangGraph agent that queries Hacker News via MCP.

State persistence:
    Conversation memory is retained across turns in interactive mode via
    LangGraph's MemorySaver checkpointer.  Every interactive session gets a
    UUID thread_id so the agent remembers what it discussed earlier in the
    same session.  One-shot mode (CLI arg) always starts a fresh thread.

Multi-service orchestration:
    By default the agent connects only to the HN Pulse MCP server (local stdio
    or remote HTTP).  Set ENABLE_FETCH=1 to also connect to the HN Fetch MCP
    server, which lets the agent read the full content of any article URL it
    finds in HN search results.

Transport modes (controlled by env vars):
    Local  (default):  server spawned as stdio subprocess
    Remote (HTTP):     MCP_SERVER_URL=http://<host>:8000/mcp/
    Fetch  server:     ENABLE_FETCH=1  (local stdio)
                    or HN_FETCH_URL=http://<host>:8001/mcp/  (remote)

Structured output (pipeline-composable):
    --output <file>   write final answer as a Markdown report
    --json            print final answer as JSON to stdout

Usage:
    python agent/agent.py                            # interactive (stateful)
    python agent/agent.py "What's trending on HN?"  # one-shot
    python agent/agent.py "..." --json               # one-shot, JSON output
    python agent/agent.py "..." --output report.md   # one-shot, file output
"""

import asyncio
import json
import os
import sys
import uuid
from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt.chat_agent_executor import create_react_agent
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

HN_PULSE_SERVER = str(Path(__file__).parent.parent / "src" / "hn_pulse" / "server.py")
HN_FETCH_SERVER = str(Path(__file__).parent.parent / "src" / "hn_extras" / "server.py")

SYSTEM_PROMPT = """\
You are an expert Hacker News research assistant with access to the HN API, \
Algolia search, and an article-fetching tool.

Use the available tools to answer questions about Hacker News stories, \
discussions, users, job listings, Ask HN posts, and Show HN projects.
When a question asks for the content or details of a linked article, use the \
fetch tool to read it before answering.

Always synthesize results into a clear, structured answer.
Cite story titles, authors, and scores when referencing specific content.
"""

console = Console()


# ── Connection config ────────────────────────────────────────────────────────

def _connection_config() -> dict:  # type: ignore[type-arg]
    """Build MultiServerMCPClient connection config.

    Includes HN Pulse (always) and optionally the HN Fetch server.
    Each service can be local stdio or remote HTTP, independently.
    """
    server_url = os.environ.get("MCP_SERVER_URL")
    config: dict = {  # type: ignore[type-arg]
        "hn_pulse": (
            {"transport": "streamable_http", "url": server_url}
            if server_url
            else {
                "transport": "stdio",
                "command": sys.executable,
                "args": [HN_PULSE_SERVER, "stdio"],
            }
        ),
    }

    # Optional second service: article URL fetcher
    fetch_url = os.environ.get("HN_FETCH_URL")
    if fetch_url:
        config["hn_fetch"] = {"transport": "streamable_http", "url": fetch_url}
    elif os.environ.get("ENABLE_FETCH"):
        config["hn_fetch"] = {
            "transport": "stdio",
            "command": sys.executable,
            "args": [HN_FETCH_SERVER, "stdio"],
        }

    return config


# ── Query runner ─────────────────────────────────────────────────────────────

async def run_query(
    query: str,
    agent,  # type: ignore[type-arg]
    thread_id: str,
    *,
    output_file: Path | None = None,
    json_output: bool = False,
) -> None:
    """Invoke the agent, display tool calls, and print/save the final answer."""
    if not json_output:
        console.print(f"\n[bold yellow]Query:[/bold yellow] {query}\n")

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": query}]},
        config={"configurable": {"thread_id": thread_id}},
    )

    messages = result.get("messages", [])
    tools_used: list[str] = []

    # Show tool calls from intermediate messages
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                tools_used.append(name)
                if not json_output:
                    args_str = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
                    preview = args_str[:80] + "…" if len(args_str) > 80 else args_str
                    console.print(
                        f"[dim]  → calling [cyan]{name}[/cyan]({preview})[/dim]"
                    )

    # Extract final answer from last AIMessage
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

    # ── Output routing ───────────────────────────────────────────────────────
    if json_output:
        payload = {
            "query": query,
            "answer": text,
            "tools_used": tools_used,
            "thread_id": thread_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "model": "claude-sonnet-4-6",
        }
        print(json.dumps(payload, indent=2))
        return

    if output_file is not None:
        report = (
            f"# HN Research Report\n\n"
            f"**Query:** {query}  \n"
            f"**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}  \n"
            f"**Tools used:** {', '.join(tools_used) or 'none'}  \n\n"
            f"---\n\n{text}\n"
        )
        output_file.write_text(report, encoding="utf-8")
        console.print(Markdown(text))
        console.print(f"\n[dim]Report saved → [cyan]{output_file}[/cyan][/dim]")
        return

    console.print(Markdown(text))


# ── Argument parsing ─────────────────────────────────────────────────────────

def _parse_args() -> tuple[str | None, Path | None, bool]:
    """Return (query | None, output_file | None, json_output)."""
    parser = ArgumentParser(
        description="HN Pulse Research Agent",
        add_help=False,  # keep --help from conflicting with queries that start with "-"
    )
    parser.add_argument("query", nargs="*", help="Research query (omit for interactive mode)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Save report to file")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    parser.add_argument("--help", "-h", action="help", help="Show this message")
    args = parser.parse_args()
    query = " ".join(args.query).strip() if args.query else None
    return query, args.output, args.json


# ── Entry point ──────────────────────────────────────────────────────────────

async def main() -> None:
    query, output_file, json_output = _parse_args()
    config = _connection_config()

    server_url = os.environ.get("MCP_SERVER_URL")
    fetch_active = bool(os.environ.get("HN_FETCH_URL") or os.environ.get("ENABLE_FETCH"))
    transport_label = f"HTTP → {server_url}" if server_url else "stdio (local)"
    services_label = f"{len(config)} service{'s' if len(config) > 1 else ''}"

    client = MultiServerMCPClient(config)
    tools = await client.get_tools()
    tool_names = [t.name for t in tools]

    if not json_output:
        console.print(
            Panel(
                f"[bold green]HN Pulse Research Agent[/bold green] "
                f"[dim](LangGraph · {transport_label} · {services_label})[/dim]\n"
                f"[dim]{len(tool_names)} tools:[/dim] "
                + "  ".join(f"[cyan]{n}[/cyan]" for n in tool_names),
                expand=False,
            )
        )
        if fetch_active:
            console.print(
                "[dim]  + article fetching enabled (HN Fetch MCP server)[/dim]\n"
            )

    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=4096)
    memory = MemorySaver()
    agent = create_react_agent(llm, tools, checkpointer=memory, prompt=SYSTEM_PROMPT)

    if query:
        # One-shot mode: independent thread per invocation
        await run_query(
            query, agent, thread_id=str(uuid.uuid4()),
            output_file=output_file, json_output=json_output,
        )
    else:
        # Interactive mode: single thread_id persists across all turns
        session_id = str(uuid.uuid4())
        console.print(
            f"[dim]Session ID: {session_id[:8]}… "
            f"(memory active — agent remembers this conversation)[/dim]\n"
            "[dim]Type your question or 'quit' to exit.[/dim]\n"
        )
        while True:
            try:
                user_input = Prompt.ask("[bold]>[/bold]").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user_input or user_input.lower() in ("quit", "exit", "q"):
                break
            await run_query(user_input, agent, thread_id=session_id)
            console.print()


if __name__ == "__main__":
    asyncio.run(main())
