#!/usr/bin/env python3
"""HN Research Agent — Claude-powered CLI for querying Hacker News via MCP.

Usage:
    python agent/agent.py                           # interactive mode
    python agent/agent.py "What's trending on HN?"  # one-shot mode
"""

import asyncio
import json
import sys
from pathlib import Path

import anthropic
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

SERVER_SCRIPT = str(Path(__file__).parent.parent / "src" / "hn_pulse" / "server.py")

SYSTEM_PROMPT = """\
You are an expert Hacker News research assistant with access to the HN API and Algolia search.

Guidelines for tool selection:
- "What's trending / top / hot" → get_top_stories
- "Latest / newest / recent submissions" → get_new_stories
- "What are people saying about X" or topic research → search_stories
- Job searches → get_job_listings (or search_stories with tags="job")
- "Show HN" / community builds → get_show_hn
- "Ask HN" / community questions → get_ask_hn
- Specific story ID or full discussion → get_story_details
- User karma / profile → get_user_profile

Always synthesize results into a clear, structured answer.
Cite story titles, authors, and scores when referencing specific content.
"""

console = Console()


def _mcp_tool_to_anthropic(tool) -> dict:
    """Convert an MCP ToolInfo object to the Anthropic tools API format."""
    return {
        "name": tool.name,
        "description": tool.description or "",
        "input_schema": tool.inputSchema or {"type": "object", "properties": {}},
    }


def _extract_text(result_content: list) -> str:
    """Extract plain text from MCP CallToolResult content."""
    parts = []
    for block in result_content:
        if hasattr(block, "text"):
            parts.append(block.text)
        else:
            parts.append(str(block))
    return "\n".join(parts)


async def run_query(query: str, session: ClientSession, anth_client: anthropic.AsyncAnthropic) -> None:
    """Run a single research query against the MCP server and stream the answer."""
    tools_result = await session.list_tools()
    tools = [_mcp_tool_to_anthropic(t) for t in tools_result.tools]

    messages: list[dict] = [{"role": "user", "content": query}]

    console.print(f"\n[bold yellow]Query:[/bold yellow] {query}\n")

    # Agentic loop: call Claude, execute tools, loop until end_turn
    while True:
        response = await anth_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )

        # Accumulate assistant turn
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Print the final answer
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    console.print(Markdown(block.text))
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                console.print(f"[dim]  → calling [cyan]{block.name}[/cyan]({_fmt_args(block.input)})[/dim]")
                try:
                    mcp_result = await session.call_tool(block.name, block.input)
                    content = _extract_text(mcp_result.content)
                except Exception as exc:
                    content = f"Error calling tool: {exc}"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason — bail out
            console.print(f"[red]Unexpected stop_reason: {response.stop_reason}[/red]")
            break


def _fmt_args(args: dict) -> str:
    """Format tool arguments compactly for display."""
    parts = [f"{k}={json.dumps(v)}" for k, v in (args or {}).items()]
    summary = ", ".join(parts)
    return summary[:80] + "…" if len(summary) > 80 else summary


async def main() -> None:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[SERVER_SCRIPT, "stdio"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]

            console.print(
                Panel(
                    f"[bold green]HN Pulse Research Agent[/bold green]\n"
                    f"[dim]Connected to hn-pulse MCP server with {len(tool_names)} tools:[/dim]\n"
                    + "  ".join(f"[cyan]{n}[/cyan]" for n in tool_names),
                    expand=False,
                )
            )

            anth_client = anthropic.AsyncAnthropic()

            if len(sys.argv) > 1:
                # One-shot mode: query from CLI args
                query = " ".join(sys.argv[1:])
                await run_query(query, session, anth_client)
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
                    await run_query(query, session, anth_client)
                    console.print()


if __name__ == "__main__":
    asyncio.run(main())
