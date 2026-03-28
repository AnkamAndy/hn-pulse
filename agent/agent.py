#!/usr/bin/env python3
"""HN Research Agent — LangGraph-powered CLI for querying Hacker News via MCP.

Uses LangGraph's create_react_agent with langchain-mcp-adapters to connect to
the HN Pulse MCP server over stdio, exposing all 8 HN tools to Claude.

Usage:
    python agent/agent.py                           # interactive mode
    python agent/agent.py "What's trending on HN?"  # one-shot mode
"""

import asyncio
import sys
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
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


async def build_agent(session: ClientSession):  # type: ignore[return]
    """Create a LangGraph ReAct agent wired to all MCP tools from the session."""
    tools = await load_mcp_tools(session)
    llm = ChatAnthropic(model="claude-sonnet-4-6", max_tokens=4096)
    return create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)


async def run_query(query: str, agent) -> None:  # type: ignore[type-arg]
    """Invoke the agent with a single query and print tool calls + final answer."""
    console.print(f"\n[bold yellow]Query:[/bold yellow] {query}\n")

    result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})

    # Show tool calls from intermediate messages
    messages = result.get("messages", [])
    for msg in messages:
        # ToolMessage has a name attribute; AIMessage may have tool_calls
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                args_str = ", ".join(f"{k}={v!r}" for k, v in (args or {}).items())
                args_preview = args_str[:80] + "…" if len(args_str) > 80 else args_str
                console.print(f"[dim]  → calling [cyan]{name}[/cyan]({args_preview})[/dim]")

    # Extract final answer from the last AIMessage
    final = messages[-1] if messages else None
    if final is None:
        console.print("[red]No response received.[/red]")
        return

    content = final.content
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "".join(
            b.get("text", "") if isinstance(b, dict) else str(b)
            for b in content
        )
    else:
        text = str(content)

    console.print(Markdown(text))


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
                    f"[bold green]HN Pulse Research Agent[/bold green] [dim](LangGraph)[/dim]\n"
                    f"[dim]Connected to hn-pulse MCP server with {len(tool_names)} tools:[/dim]\n"
                    + "  ".join(f"[cyan]{n}[/cyan]" for n in tool_names),
                    expand=False,
                )
            )

            agent = await build_agent(session)

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
