# HN Pulse — Project Spec

> A complete spec-driven development prompt. Paste the block in **Section 8** into
> Claude Code (or any capable coding agent) and it will plan, validate, then build
> the entire HN Pulse project step by step — without writing a line of code until
> the plan is approved.

---

## How to use this spec

1. Open a fresh Claude Code session in an empty directory
2. Copy the prompt from **Section 8 — Full Prompt** at the bottom of this file
3. Paste it as your first message
4. Review the plan the agent produces — push back on anything that doesn't match your intent
5. Approve the plan, then let the agent execute step by step

The prompt enforces **spec-driven development**:
- Plan is written and reviewed before any code is written
- Each step has a verifiable exit condition (a command that must exit 0)
- Acceptance criteria are binary — implementation is not "done" until all pass

---

## Section 1 — Identity & Goal

| Field | Value |
|-------|-------|
| **Project** | HN Pulse |
| **Purpose** | Expose the Hacker News public API as an MCP Server so any MCP-compatible AI assistant can query HN stories, search discussions, look up users, and find jobs via natural language |
| **Framework** | arcade-mcp (scaffold with `arcade new hn_pulse`) |
| **Agent** | Claude-powered CLI research agent (Anthropic SDK + MCP stdio transport) |
| **Primary API** | HN Firebase — `hacker-news.firebaseio.com/v0` |
| **Search API** | Algolia HN Search — `hn.algolia.com/api/v1` |
| **Auth** | None — both APIs are public and free |

---

## Section 2 — Hard Constraints

These constraints encode architectural decisions that must not be "optimised away":

| # | Constraint | Reason |
|---|-----------|--------|
| 1 | Tools **must** be plain `async def` functions — no `@app.tool` decorator. Register via `app.add_tool()` in `server.py` only. | Unit tests call tool functions directly without constructing an MCPApp. Decorating at import time couples every module to a live framework instance. |
| 2 | All feed tools **must** use `asyncio.gather` for concurrent item fetches. | HN Firebase returns only ID arrays from feed endpoints. Sequential fetching = N+1 RTTs. `gather` collapses to 2 RTTs (~300ms vs ~3s for 10 stories). |
| 3 | Algolia results **must** be cleaned before returning. Strip: `_highlightResult`, `children`, `_tags`, `updated_at`. Target: ~200 bytes/result (down from ~2KB raw). | 20 results = 36KB raw → 4KB clean. A 9× token reduction per search call. |
| 4 | Transport **must** be stdio (subprocess spawn). No HTTP server, no open ports, no auth tokens on the wire. | Safest local transport. Process lifecycle tied to agent. How Claude Desktop integrates MCP servers natively. |
| 5 | No caching layer in v1. | Correctness over optimisation within the time constraint. |
| 6 | Tests are mandatory in three tiers — see Section 5. | |
| 7 | Python 3.10+. Package manager: `uv`. Linter: `ruff`. | |

---

## Section 3 — Tools Spec (8 total)

### `src/hn_pulse/tools/stories.py`

```
get_top_stories(count: int = 10) -> list[dict]
  - Fetch /v0/topstories.json → ID array
  - Fetch each item concurrently via asyncio.gather
  - Return: id, title, url, score, by, descendants, time
  - count clamp: 1–30

get_new_stories(count: int = 10) -> list[dict]
  - Same pattern using /v0/newstories.json
```

### `src/hn_pulse/tools/item.py`

```
get_story_details(
  story_id: int,
  max_comments: int = 10,
  include_replies: bool = False
) -> dict
  - Fetch /v0/item/{id}.json
  - Fetch top-level comments concurrently (up to max_comments)
  - Filter out deleted=True and dead=True comments
  - If include_replies: fetch one level of kids per comment
  - Return: full story fields + filtered comments list
```

### `src/hn_pulse/tools/search.py`

```
search_stories(
  query: str,
  sort_by: Literal["relevance", "date"] = "relevance",
  tags: str = "story",
  num_results: int = 10,
  page: int = 0
) -> list[dict]
  - Call Algolia /api/v1/search or /api/v1/search_by_date
  - Run _clean_hit() on every result before returning
  - _clean_hit keeps: story_id, title, url, author, points,
    num_comments, created_at, text (story_text or comment_text)
```

### `src/hn_pulse/tools/users.py`

```
get_user_profile(
  username: str,
  include_recent_submissions: bool = False
) -> dict
  - Fetch /v0/user/{id}.json
  - Truncate submitted list to 10 IDs if include_recent_submissions
  - Return: id, karma, about, created, recent_submissions
```

### `src/hn_pulse/tools/specials.py`

```
get_job_listings(count: int = 10) -> list[dict]
  - /v0/jobstories.json → fetch items concurrently

get_ask_hn(count: int = 10) -> list[dict]
  - /v0/askstories.json → fetch items concurrently

get_show_hn(count: int = 10) -> list[dict]
  - /v0/showstories.json → fetch items concurrently
```

---

## Section 4 — Architecture

```
src/hn_pulse/
  client.py      — hn_client() and algolia_client() factory functions
                   using httpx.AsyncClient. Single seam for pytest-httpx.
  server.py      — MCPApp("HnPulse"). Imports ALL_TOOLS. Calls
                   app.add_tool(fn) for each. Stdio transport.
  tools/
    __init__.py  — exports ALL_TOOLS: list of all 8 functions
    stories.py / item.py / search.py / users.py / specials.py

agent/
  agent.py       — Anthropic SDK explicit tool-use loop (NOT tool_runner()).
                   Spawns server.py via StdioServerParameters.
                   Interactive mode + one-shot mode (sys.argv[1]).
                   Uses rich for output.
                   Loop: send → check stop_reason → collect tool_use blocks
                   → call via MCP → append tool_result → repeat until end_turn.

.claude/
  commands/
    hn-research.md  — /hn-research: checks key, checks install, runs agent
    run-evals.md    — /run-evals: tier runner (unit|integration|eval)

docs/
  spec.md              — this file
  systems-design.html  — interactive architecture diagram
```

**Key architectural rule:** framework coupling happens in exactly one place (`server.py`). Every other file is plain Python.

---

## Section 5 — Testing Spec

### Tier 1 — Unit tests (`tests/unit/`) — `$0 · <1s`

- **Tool:** `pytest` + `pytest-httpx` (intercepts `httpx` at transport layer)
- **Method:** Call tool functions directly — `await get_top_stories(count=2)`
- **Coverage required:**
  - count clamping (min 1, max 30)
  - null/missing item filtering
  - `deleted=True` and `dead=True` comment filtering
  - `_clean_hit` strips all forbidden fields
  - `asyncio.gather` fires all item fetches (verify N mock calls registered)
  - Algolia `sort_by` routes to correct endpoint
  - user `submitted` list truncated to 10

### Tier 2 — Integration tests (`tests/integration/`) — `$0 · 3–5s` — `@pytest.mark.integration`

- **Tool:** `mcp` Python SDK (real subprocess)
- **Method:** Start `server.py` as subprocess via `StdioServerParameters`, perform full MCP handshake, call `list_tools()`
- **Assertions:**
  - Exactly 8 tools registered
  - Tool names match expected set (arcade-mcp prefixes: `HnPulse_GetTopStories` etc.)
  - Every tool has a non-empty description
  - Every tool `inputSchema` has `type: "object"`

### Tier 3 — Eval tests (`tests/evals/`) — `~$0.002 · ~15s` — `@pytest.mark.eval`

- **Tool:** Anthropic API (`claude-haiku` — cheapest model)
- **Method:** Pass each query with all 8 tool schemas. Use `tool_choice={"type": "any"}` to force selection. Assert correct tool chosen.
- **10 required cases:**

| Query | Expected tool |
|-------|--------------|
| "What is trending on HN right now?" | `get_top_stories` |
| "Show me the latest submitted stories" | `get_new_stories` |
| "Get details for story 12345" | `get_story_details` |
| "What are people saying about Rust in 2025?" | `search_stories` |
| "Find recent comments about TypeScript" | `search_stories` |
| "What is user pg's karma and bio?" | `get_user_profile` |
| "Find current job postings on HN" | `get_job_listings` |
| "What questions is the HN community asking?" | `get_ask_hn` |
| "Show me what developers are building" | `get_show_hn` |
| "Search for posts about LLM infrastructure" | `search_stories` |

---

## Section 6 — Acceptance Criteria

Implementation is not complete until **all** of the following pass:

```
[ ] arcade new hn_pulse scaffolds without error
[ ] uv pip install -e ".[agent,dev]" succeeds with no conflicts
[ ] pytest -m "not eval" -v  →  all unit + integration tests pass
[ ] pytest -m eval -v        →  ≥ 9/10 eval cases pass
[ ] python agent/agent.py "What is trending on HN?"
      returns a synthesised answer using at least one tool call
[ ] /hn-research skill: running without ANTHROPIC_API_KEY prints
      a clear fix instruction and exits non-zero
[ ] /run-evals unit: runs unit tier only and exits 0
[ ] README contains all required sections:
      Installation, Running Agent, Claude Code Skills,
      Running Tests, Project Structure, Design Notes
[ ] git log shows clean commit history (no "Co-Authored-By: Claude")
```

---

## Section 7 — Execution Order

Follow this order exactly. State what was completed and what comes next after each step. **Do not write code for step N+1 until step N's verification command passes.**

| Step | Action | Verification |
|------|--------|-------------|
| 1 | Scaffold: `arcade new hn_pulse` | Inspect generated files; note actual package name |
| 2 | Update `pyproject.toml` — add optional deps, pytest markers, `asyncio_mode = "auto"` | `uv pip install -e ".[agent,dev]"` exits 0 |
| 3 | Implement `client.py` + all 8 tool functions | `ruff check src/` — zero errors |
| 4 | Implement `server.py` — wire ALL_TOOLS | `python src/hn_pulse/server.py` starts silently |
| 5 | Write + run unit tests | `pytest tests/unit/ -v` — all pass |
| 6 | Write + run integration tests | `pytest -m integration -v` — all pass |
| 7 | Implement `agent/agent.py` | `python agent/agent.py "What is trending?"` returns answer |
| 8 | Write + run eval tests | `pytest -m eval -v` — ≥ 9/10 pass |
| 9 | Write Claude Code skills | `/hn-research` and `/run-evals` skills work correctly |
| 10 | Write README + `docs/systems-design.html` | All required README sections present |
| 11 | Run full acceptance criteria checklist | Every item in Section 6 checks off |
| 12 | Commit + push (specific files only, no `git add -A`) | `git log` shows clean history |

---

## Section 8 — Full Prompt

Copy everything between the `---` markers below and paste it as your first message in a new Claude Code session:

---

```
You are building a production-quality MCP Server and research agent from scratch.
Follow spec-driven development: read the full spec, write a plan, validate the
plan against the acceptance criteria, then implement step by step. Do not write
any code until the plan is approved.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — IDENTITY & GOAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Project:   HN Pulse
Purpose:   Expose the Hacker News public API as an MCP Server so any
           MCP-compatible AI assistant can query HN stories, search
           discussions, look up users, and find jobs — all via natural
           language.
Framework: arcade-mcp (scaffold with `arcade new hn_pulse`)
Agent:     Claude-powered CLI research agent (Anthropic SDK + MCP stdio)
APIs:      HN Firebase (hacker-news.firebaseio.com/v0)
           Algolia HN Search (hn.algolia.com/api/v1)
Auth:      None — both APIs are public and free

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — HARD CONSTRAINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Tools MUST be plain async functions — no @app.tool decorator.
   Register all tools via app.add_tool() in server.py only.
   Reason: unit tests must call tool functions directly without
   constructing an MCPApp.

2. All feed tools MUST use asyncio.gather for concurrent item fetches.
   The HN Firebase API returns only ID arrays from feed endpoints.
   Sequential fetching produces N+1 RTTs. gather collapses to 2 RTTs.

3. Algolia results MUST be cleaned before returning.
   Strip: _highlightResult, children, _tags, updated_at.
   Target: ~200 bytes/result (down from ~2KB raw).

4. Transport MUST be stdio (subprocess spawn).
   No HTTP server, no open ports, no auth tokens on the wire.

5. No caching layer in v1. Correctness over optimization.

6. Tests are mandatory in three tiers — see Section 5.

7. Python 3.10+. Package manager: uv. Linter: ruff.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — TOOLS SPEC (8 total)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

File: src/hn_pulse/tools/stories.py
  get_top_stories(count: int = 10) -> list[dict]
    - Fetch /v0/topstories.json → ID array
    - Fetch each item concurrently via asyncio.gather
    - Return: id, title, url, score, by, descendants, time
    - count clamp: 1–30

  get_new_stories(count: int = 10) -> list[dict]
    - Same pattern using /v0/newstories.json

File: src/hn_pulse/tools/item.py
  get_story_details(
    story_id: int,
    max_comments: int = 10,
    include_replies: bool = False
  ) -> dict
    - Fetch /v0/item/{id}.json
    - Fetch top-level comments concurrently (up to max_comments)
    - Filter out deleted=True and dead=True comments
    - If include_replies: fetch one level of kids per comment
    - Return: full story fields + filtered comments list

File: src/hn_pulse/tools/search.py
  search_stories(
    query: str,
    sort_by: Literal["relevance", "date"] = "relevance",
    tags: str = "story",
    num_results: int = 10,
    page: int = 0
  ) -> list[dict]
    - Call Algolia /api/v1/search or /api/v1/search_by_date
    - Run _clean_hit() on every result before returning
    - _clean_hit keeps: story_id, title, url, author, points,
      num_comments, created_at, text (story_text or comment_text)

File: src/hn_pulse/tools/users.py
  get_user_profile(
    username: str,
    include_recent_submissions: bool = False
  ) -> dict
    - Fetch /v0/user/{id}.json
    - Truncate submitted list to 10 IDs if include_recent_submissions
    - Return: id, karma, about, created, recent_submissions

File: src/hn_pulse/tools/specials.py
  get_job_listings(count: int = 10) -> list[dict]
    - /v0/jobstories.json → fetch items concurrently

  get_ask_hn(count: int = 10) -> list[dict]
    - /v0/askstories.json → fetch items concurrently

  get_show_hn(count: int = 10) -> list[dict]
    - /v0/showstories.json → fetch items concurrently

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

src/hn_pulse/
  client.py      — hn_client() and algolia_client() factory functions
                   using httpx.AsyncClient. This is the single seam
                   pytest-httpx intercepts in unit tests.
  server.py      — MCPApp("HnPulse"). Imports ALL_TOOLS from tools/__init__.py
                   Calls app.add_tool(fn) for each. Runs stdio transport.
  tools/
    __init__.py  — exports ALL_TOOLS: list of all 8 functions
    stories.py / item.py / search.py / users.py / specials.py

agent/
  agent.py       — Anthropic SDK explicit tool-use loop (NOT tool_runner()).
                   Spawns server.py as subprocess via StdioServerParameters.
                   Supports interactive mode and one-shot mode (sys.argv[1]).
                   Uses rich for output. Accumulates messages across turns.
                   Loop: send → check stop_reason → collect tool_use blocks
                   → call via MCP → append tool_result → repeat until end_turn.

.claude/
  commands/
    hn-research.md  — /hn-research skill: checks ANTHROPIC_API_KEY,
                      checks package installed, runs agent in one-shot mode
    run-evals.md    — /run-evals skill: three-tier runner with optional
                      tier arg (unit|integration|eval), graceful key handling

docs/
  spec.md              — this spec file
  systems-design.html  — self-contained HTML architecture diagram

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — TESTING SPEC (three tiers)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIER 1 — Unit tests (tests/unit/)
  Tool:    pytest + pytest-httpx (intercepts httpx at transport layer)
  Cost:    $0
  Speed:   < 1s
  Method:  Call tool functions directly: await get_top_stories(count=2)
           Mock HTTP responses via httpx_mock fixture
  Cover:
    - count clamping (min 1, max 30)
    - null/missing item filtering
    - deleted=True and dead=True comment filtering
    - _clean_hit strips all forbidden fields
    - asyncio.gather fires all item fetches (verify N mock calls registered)
    - Algolia sort_by routes to correct endpoint
    - user submitted list truncated to 10

TIER 2 — Integration tests (tests/integration/)  @pytest.mark.integration
  Tool:    mcp Python SDK (real subprocess)
  Cost:    $0
  Speed:   3–5s
  Method:  Start server.py as subprocess via StdioServerParameters
           Perform full MCP handshake, call list_tools()
  Assert:
    - Exactly 8 tools registered
    - Tool names match expected set (note arcade-mcp prefixes:
      HnPulse_GetTopStories etc.)
    - Every tool has a non-empty description
    - Every tool inputSchema has type: "object"

TIER 3 — Eval tests (tests/evals/)  @pytest.mark.eval
  Tool:    Anthropic API (claude-haiku — cheapest model)
  Cost:    ~$0.002 total for 10 cases
  Speed:   ~15s
  Method:  Pass each query to claude-haiku with all 8 tool schemas.
           Use tool_choice={"type": "any"} to force tool selection.
           Assert model selected expected tool.
  10 cases (query → expected_tool):
    "What is trending on HN right now?"          → get_top_stories
    "Show me the latest submitted stories"        → get_new_stories
    "Get details for story 12345"                 → get_story_details
    "What are people saying about Rust in 2025?"  → search_stories
    "Find recent comments about TypeScript"        → search_stories
    "What is user pg's karma and bio?"             → get_user_profile
    "Find current job postings on HN"              → get_job_listings
    "What questions is the HN community asking?"   → get_ask_hn
    "Show me what developers are building"         → get_show_hn
    "Search for posts about LLM infrastructure"    → search_stories

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 6 — ACCEPTANCE CRITERIA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

The plan is complete and implementation may begin only when ALL of
the following are satisfiable:

[ ] arcade new hn_pulse scaffolds without error
[ ] uv pip install -e ".[agent,dev]" succeeds with no conflicts
[ ] pytest -m "not eval" -v → all unit + integration tests pass
[ ] pytest -m eval -v → ≥ 9/10 eval cases pass
[ ] python agent/agent.py "What is trending on HN?" returns
    a synthesised answer using at least one tool call
[ ] /hn-research skill validates missing API key correctly
[ ] /run-evals unit runs unit tier only and exits 0
[ ] README contains: Installation, Running Agent, Claude Code Skills,
    Running Tests, Project Structure, Design Notes sections
[ ] git log shows clean commit history (no "Co-Authored-By: Claude")

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 7 — EXECUTION ORDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Follow this exact order. Do not skip ahead. After each step, state
what was completed and what comes next.

Step 1 — Scaffold
  arcade new hn_pulse && cd hn_pulse
  Inspect generated files. Note actual package name and deps.

Step 2 — pyproject.toml
  Add optional deps: agent (anthropic, mcp, rich), dev (pytest,
  pytest-asyncio, pytest-httpx, ruff, mypy)
  Add pytest markers: integration, eval
  asyncio_mode = "auto"

Step 3 — Core: client.py + tools/ (all 8 functions)
  Implement per spec. No server wiring yet.
  Run ruff check src/ — fix all lint errors before moving on.

Step 4 — server.py
  Wire ALL_TOOLS via app.add_tool(). Stdio transport only.
  Smoke test: python src/hn_pulse/server.py — should start silently.

Step 5 — Unit tests
  Write all unit tests. Run pytest tests/unit/ -v.
  All must pass before Step 6.

Step 6 — Integration tests
  Write integration tests. Run pytest -m integration -v.
  Confirm tool name prefixing matches actual arcade-mcp behaviour.

Step 7 — agent/agent.py
  Explicit tool-use loop. Interactive + one-shot modes.
  Test: python agent/agent.py "What is trending on HN today?"

Step 8 — Eval tests
  Write 10 parametrized eval cases. Run pytest -m eval -v.
  Target ≥ 9/10.

Step 9 — Claude Code skills
  .claude/commands/hn-research.md
  .claude/commands/run-evals.md
  Per spec in Section 4.

Step 10 — Documentation
  README.md with all required sections.
  docs/systems-design.html.

Step 11 — Final validation
  Run full acceptance criteria checklist from Section 6.
  Fix anything that fails. Do not commit until all criteria pass.

Step 12 — Commit & push
  git add (specific files only — never git add -A)
  Single clean commit. No Co-Authored-By trailer.
  gh repo create hn-pulse --public && git push -u origin main

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Now write the implementation plan. For each step, state:
  - What files will be created or modified
  - Any risk or ambiguity to resolve before coding
  - The specific command used to verify the step is complete

Do not write any code yet. Present the plan for review.
```

---

*This spec was used to build the initial version of HN Pulse. See [systems-design.html](systems-design.html) for the architecture diagram and design trade-off analysis.*
