"""Integration tests — verifies MCP server starts and advertises correct tools."""

import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

SERVER_SCRIPT = str(Path(__file__).parent.parent.parent / "src" / "hn_pulse" / "server.py")

# arcade-mcp registers tools as {ToolkitName}_{FunctionName} in PascalCase.
# MCPApp name "hn_pulse" → toolkit prefix "HnPulse".
EXPECTED_TOOLS = {
    "HnPulse_GetTopStories",
    "HnPulse_GetNewStories",
    "HnPulse_GetStoryDetails",
    "HnPulse_SearchStories",
    "HnPulse_GetUserProfile",
    "HnPulse_GetJobListings",
    "HnPulse_GetAskHn",
    "HnPulse_GetShowHn",
}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_server_lists_all_expected_tools():
    """MCP server must start and advertise exactly the 8 expected tools."""
    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT, "stdio"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        tool_names = {t.name for t in result.tools}
        assert tool_names == EXPECTED_TOOLS, (
            f"Unexpected tools. Missing: {EXPECTED_TOOLS - tool_names}. "
            f"Extra: {tool_names - EXPECTED_TOOLS}"
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_all_tools_have_descriptions():
    """Every tool must have a non-empty description for LLMs to understand its purpose."""
    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT, "stdio"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        for tool in result.tools:
            assert tool.description, f"Tool '{tool.name}' is missing a description"
            assert len(tool.description.strip()) > 10, (
                f"Tool '{tool.name}' description is too short: '{tool.description}'"
            )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_all_tools_have_input_schemas():
    """Every tool must have a valid JSON schema so MCP clients can generate correct inputs."""
    params = StdioServerParameters(command=sys.executable, args=[SERVER_SCRIPT, "stdio"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.list_tools()
        for tool in result.tools:
            assert tool.inputSchema is not None, (
                f"Tool '{tool.name}' is missing an input schema"
            )
            assert tool.inputSchema.get("type") == "object", (
                f"Tool '{tool.name}' schema root must be type=object"
            )
