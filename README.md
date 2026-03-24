# HN Pulse

A **Hacker News MCP Server** built with [arcade-mcp](https://github.com/ArcadeAI/arcade-mcp), plus a Claude-powered research agent that uses it.

HN Pulse gives any MCP-compatible AI assistant (Claude Desktop, Cursor, VS Code) direct read access to Hacker News — top stories, search, comments, user profiles, job listings, Ask HN, and Show HN — all via the public HN Firebase and Algolia APIs. No API keys required for the server.

---

## What It Does

| Tool | Description |
|------|-------------|
| `get_top_stories` | Top N HN stories by ranking |
| `get_new_stories` | Most recently submitted stories |
| `get_story_details` | Full story with filtered comment tree |
| `search_stories` | Algolia full-text search across HN |
| `get_user_profile` | Karma, about text, and account age |
| `get_job_listings` | Current HN job postings |
| `get_ask_hn` | Recent Ask HN posts |
| `get_show_hn` | Recent Show HN posts |

The included **research agent** wraps these tools with Claude to answer natural-language queries like:

- *"What's the HN community saying about Rust in 2025?"*
- *"Find recent AI startup job listings"*
- *"Summarise the top Show HN projects this week"*
- *"What is user pg's about section?"*

---

## Architecture

```
User → agent/agent.py ──stdio──► src/hn_pulse/server.py
                                        │
                          ┌─────────────┼─────────────────┐
                          ▼             ▼                   ▼
              HN Firebase API    Algolia HN Search    (no auth needed)
          hacker-news.firebaseio.com  hn.algolia.com/api/v1
```

The agent spawns the MCP server as a subprocess, connects via stdio transport, then runs a standard Claude tool-use loop: Claude chooses a tool → agent calls it via MCP → result fed back to Claude → loop until `end_turn`.

---

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) — `brew install uv`
- Anthropic API key — only for the research agent

---

## Installation

```bash
git clone https://github.com/<your-username>/hn-pulse.git
cd hn-pulse

# Create virtual environment and install all dependencies
uv venv
uv pip install -e ".[agent,dev]"

# Copy env template
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY (only needed for the agent)
```

---

## Running the MCP Server

### stdio transport (for Claude Desktop, CLI tools)

```bash
uv run src/hn_pulse/server.py stdio
# or simply:
uv run src/hn_pulse/server.py
```

### HTTP transport (for Cursor, VS Code)

```bash
uv run src/hn_pulse/server.py http
# API docs available at http://127.0.0.1:8000/docs
```

### Connect to Claude Desktop

```bash
# Install arcade CLI if you haven't already
uv tool install arcade-mcp

# Auto-configure Claude Desktop to use this server
arcade configure claude
```

---

## Running the Research Agent

```bash
# Interactive mode
python agent/agent.py

# One-shot mode
python agent/agent.py "What are people saying about Rust in 2025?"
python agent/agent.py "Find ML job postings on HN"
python agent/agent.py "Summarize the top Show HN projects this week"
```

The agent connects to the MCP server automatically via stdio.

---

## Running Tests

```bash
# Unit tests — zero API cost, mocked HTTP
pytest tests/unit/ -v

# Integration tests — starts the real server, zero API cost
pytest tests/integration/ -m integration -v

# Eval tests — requires ANTHROPIC_API_KEY, ~$0.002 total (uses claude-haiku)
pytest tests/evals/ -m eval -v

# All tests except evals
pytest -m "not eval" -v
```

### Test Coverage

| Suite | Count | What it validates |
|-------|-------|-------------------|
| Unit | 22 tests | Each tool function in isolation (mocked HTTP via pytest-httpx) |
| Integration | 3 tests | MCP server starts, all 8 tools registered with valid schemas |
| Evals | 10 parametrized cases | Claude selects the correct tool for 10 natural-language queries |

---

## Project Structure

```
hn-pulse/
├── src/hn_pulse/
│   ├── server.py          # MCPApp entrypoint — registers all tools
│   ├── client.py          # httpx client factory (HN + Algolia)
│   └── tools/
│       ├── stories.py     # get_top_stories, get_new_stories
│       ├── item.py        # get_story_details
│       ├── search.py      # search_stories (Algolia)
│       ├── users.py       # get_user_profile
│       └── specials.py    # get_job_listings, get_ask_hn, get_show_hn
├── agent/
│   └── agent.py           # Claude research agent (stdio MCP client)
├── tests/
│   ├── unit/              # pytest-httpx mocked tool tests
│   ├── integration/       # real MCP server startup tests
│   └── evals/             # Claude tool-selection accuracy tests
├── pyproject.toml
└── .env.example
```

---

## Design Notes

**Tools as plain async functions**: Each tool is a regular Python `async def` — no framework decorators. They're registered with `app.add_tool()` in `server.py`. This makes unit testing trivial: call `await get_top_stories(count=5)` directly without an MCP server.

**Concurrent item fetches**: The HN Firebase API returns only ID arrays from feed endpoints. Fetching N stories naively would require N sequential round trips. All tools use `asyncio.gather()` to fetch items in parallel, reducing latency to ~2 round trips regardless of count.

**Algolia metadata stripping**: Algolia search results include `_highlightResult`, `children` (arrays of comment IDs), and other metadata that bloat LLM context. `_clean_hit()` strips these before returning, reducing each result from ~2 KB to ~200 bytes.

---

## External Resources & Attribution

- [Hacker News API](https://github.com/HackerNews/API) — Firebase REST API (public, no auth)
- [Algolia HN Search API](https://hn.algolia.com/api) — Full-text search (public, no auth)
- [arcade-mcp](https://github.com/ArcadeAI/arcade-mcp) — MCP server framework
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) — Claude API client
- [mcp Python SDK](https://github.com/modelcontextprotocol/python-sdk) — MCP protocol client

---

## License

MIT
