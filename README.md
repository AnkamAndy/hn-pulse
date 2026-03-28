# HN Pulse

[![CI](https://github.com/AnkamAndy/hn-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/AnkamAndy/hn-pulse/actions/workflows/ci.yml)

A **Hacker News MCP Server** built with [arcade-mcp](https://github.com/ArcadeAI/arcade-mcp), plus a Claude-powered research agent that uses it.

HN Pulse gives any MCP-compatible AI assistant (Claude Desktop, Cursor, VS Code) direct read access to Hacker News — top stories, search, comments, user profiles, job listings, Ask HN, and Show HN — all via the public HN Firebase and Algolia APIs. No API keys required for the server.

---

## What It Does

**HN Pulse MCP Server** — 8 tools:

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

**HN Fetch MCP Server** — 1 supplementary tool (second service):

| Tool | Description |
|------|-------------|
| `fetch_article` | Fetches the full text of any article URL |

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

The agent spawns the MCP server as a subprocess, connects via stdio transport, then uses **LangGraph's `create_react_agent`** with `langchain-mcp-adapters` to bridge MCP tools into a standard ReAct loop: Claude chooses a tool → agent calls it via MCP → result fed back to Claude → loop until done.

**Conversation state** is persisted across turns in interactive mode via LangGraph's `MemorySaver` checkpointer — the agent remembers what it said earlier in the same session. Each session gets a UUID `thread_id`. One-shot mode always starts a fresh thread.

**Multi-service**: when `ENABLE_FETCH=1` is set, the agent also connects to the HN Fetch MCP server, allowing Claude to read full article content from any HN story URL.

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

### Local mode (default — server spawned as subprocess)

```bash
# Interactive mode — stateful (agent remembers the conversation)
python agent/agent.py

# One-shot mode
python agent/agent.py "What are people saying about Rust in 2025?"

# One-shot with structured output (pipeline-composable)
python agent/agent.py "Summarise top AI stories" --output report.md
python agent/agent.py "What's trending?" --json

# Enable multi-service: also connect the URL fetch server
ENABLE_FETCH=1 python agent/agent.py "What does the top HN story say?"
```

The agent spawns the MCP server(s) automatically as subprocesses via stdio.

### Remote mode (server on a different machine)

Start the server on the remote machine, binding to all network interfaces:

```bash
# On the remote machine (replace 8000 with your preferred port)
uv run src/hn_pulse/server.py http --host 0.0.0.0 --port 8000
```

Then point the agent at it using `MCP_SERVER_URL`:

```bash
# On the client machine
export MCP_SERVER_URL=http://<remote-ip>:8000/mcp/
python agent/agent.py "What's trending on HN today?"
```

The agent automatically switches from stdio to HTTP transport when `MCP_SERVER_URL` is set — no code changes needed. The MCP endpoint is always at `/mcp/`.

### Docker deployment (both services)

```bash
# Build and start both MCP servers as containers
docker compose up --build

# Run the agent against the deployed services
MCP_SERVER_URL=http://localhost:8000/mcp/ \
HN_FETCH_URL=http://localhost:8001/mcp/ \
ANTHROPIC_API_KEY=sk-... \
python agent/agent.py "Summarise the top story and read its full article"
```

`docker-compose.yml` starts two services: `hn-server` (port 8000) and `fetch-server` (port 8001), each with health checks. Both are built from the same `Dockerfile`.

---

## Claude Code Skills

If you are using [Claude Code](https://claude.ai/code), two slash commands are available after cloning:

| Skill | What it does |
|-------|-------------|
| `/hn-research <query>` | Validates prerequisites and runs the research agent in one-shot mode |
| `/run-evals [unit\|integration\|eval]` | Runs the full test suite or a specific tier |

**Examples:**
```
/hn-research What are people saying about Rust in 2025?
/run-evals
/run-evals unit
/run-evals eval
```

Both skills check for `ANTHROPIC_API_KEY` and print clear fix instructions if it is missing. Skills are defined in `.claude/commands/`.

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

Or use the **Makefile** shortcuts:

```bash
make install       # install all deps
make test          # unit + integration (no API key needed)
make test-eval     # eval tier only (requires ANTHROPIC_API_KEY)
make lint          # ruff check
make typecheck     # mypy
make check         # lint + typecheck + test (full local CI)
```

### Test Coverage

| Suite | Count | What it validates |
|-------|-------|-------------------|
| Unit | 51 tests | Each tool function in isolation — happy path + error scenarios (mocked HTTP via pytest-httpx) |
| Integration | 3 tests | MCP server starts, all 8 tools registered with valid schemas |
| Evals | 10 parametrized cases | Claude selects the correct tool for 10 natural-language queries |

---

## Project Structure

```
hn-pulse/
├── .claude/
│   └── commands/
│       ├── hn-research.md     # /hn-research — runs the research agent
│       └── run-evals.md       # /run-evals — three-tier test runner
├── .github/
│   └── workflows/
│       └── ci.yml             # CI: lint + typecheck + tests on PR; evals on main
├── src/
│   ├── hn_pulse/
│   │   ├── server.py      # MCPApp entrypoint — registers all 8 tools
│   │   ├── client.py      # httpx client factory (HN + Algolia)
│   │   ├── types.py       # TypedDict definitions (Story, SearchResponse, …)
│   │   └── tools/
│   │       ├── common.py  # Shared fetch_item, gather_items, constants
│   │       ├── stories.py # get_top_stories, get_new_stories
│   │       ├── item.py    # get_story_details
│   │       ├── search.py  # search_stories (Algolia)
│   │       ├── users.py   # get_user_profile
│   │       └── specials.py # get_job_listings, get_ask_hn, get_show_hn
│   └── hn_extras/
│       ├── fetch.py       # fetch_article tool (HTML → plain text)
│       └── server.py      # Second MCPApp — URL article fetcher
├── agent/
│   └── agent.py           # Stateful LangGraph agent — multi-service, --output/--json
├── tests/
│   ├── unit/              # pytest-httpx mocked tests (51 total, incl. error scenarios)
│   ├── integration/       # real MCP server startup tests
│   └── evals/             # Claude tool-selection accuracy tests
├── docs/
│   ├── spec.md            # Spec-driven development prompt to recreate this project
│   └── systems-design.html # Architecture diagram + design trade-offs
├── Dockerfile             # Single image for both MCP servers
├── docker-compose.yml     # hn-server (8000) + fetch-server (8001)
├── Makefile               # make check, make test, make lint, make typecheck
├── .pre-commit-config.yaml
├── pyproject.toml
└── .env.example
```

---

## Design Notes

**Tools as plain async functions**: Each tool is a regular Python `async def` — no framework decorators. They're registered with `app.add_tool()` in `server.py`. This makes unit testing trivial: call `await get_top_stories(count=5)` directly without an MCP server.

**Concurrent item fetches**: The HN Firebase API returns only ID arrays from feed endpoints. Fetching N stories naively would require N sequential round trips. All tools use `asyncio.gather()` to fetch items in parallel, reducing latency to ~2 round trips regardless of count.

**Algolia metadata stripping**: Algolia search results include `_highlightResult`, `children` (arrays of comment IDs), and other metadata that bloat LLM context. `_clean_hit()` strips these before returning, reducing each result from ~2 KB to ~200 bytes.

**Shared helpers** (`tools/common.py`): `fetch_item` and `gather_items` are the single canonical implementations used by all feed tools — no duplicate private helpers. Constants (`MAX_STORY_COUNT`, etc.) live here so magic numbers never appear in tool files.

**LangGraph agent**: `agent/agent.py` uses `create_react_agent` from LangGraph with `MultiServerMCPClient` from `langchain-mcp-adapters` — the same pattern used by ArcadeAI reference projects. `MemorySaver` + `thread_id` gives the interactive agent persistent conversation memory across turns.

**Multi-service orchestration**: `MultiServerMCPClient` connects to both `hn_pulse` and `hn_fetch` simultaneously. The agent can search HN for a story and then fetch the full article in a single reasoning loop — each service independently local or remote.

**Structured deliverables**: `--output report.md` writes a formatted Markdown report; `--json` prints a structured payload (`query`, `answer`, `tools_used`, `timestamp`) for downstream pipeline consumption.

**Containerised**: `Dockerfile` + `docker-compose.yml` deploy both MCP servers as isolated containers with health checks. `docker compose up --build` replaces the entire manual venv/install flow.

For the full spec used to build this project (suitable for reproducing it with an AI coding agent), see [docs/spec.md](docs/spec.md).

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
