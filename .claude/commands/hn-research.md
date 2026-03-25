# /hn-research

Run the HN Pulse research agent with a natural language query.

## Usage

```
/hn-research <query>
```

**Examples:**
- `/hn-research What's trending on HN today?`
- `/hn-research What are people saying about Rust in 2025?`
- `/hn-research Find recent AI infrastructure job postings`

---

## What this skill does

1. **Checks prerequisites** — verifies `ANTHROPIC_API_KEY` is set and the package is installed before running anything. Prints a clear fix if either is missing.
2. **Runs the agent** — spawns `agent/agent.py` with your query in one-shot mode (non-interactive, prints the final answer and exits).
3. **Reports tool calls** — the agent prints each MCP tool it invokes so you can see exactly which of the 8 HN tools Claude selected.

---

## Steps

Check that ANTHROPIC_API_KEY is set in the environment. If it is not set or is empty, stop and print this exact message:

```
✗  ANTHROPIC_API_KEY is not set.
   Run:  export ANTHROPIC_API_KEY=your_key_here
   Or:   copy .env.example → .env and fill in your key, then: source .env
```

Check that the package is installed by running:
```
uv run python -c "import hn_pulse" 2>/dev/null
```
If that fails, stop and print:
```
✗  hn_pulse package not found.
   Run:  uv pip install -e ".[agent,dev]"
```

Extract the query from the arguments passed to this skill (everything after `/hn-research`). If no query was provided, stop and print:
```
✗  No query provided.
   Usage:  /hn-research <your question>
   Example: /hn-research What is trending on HN today?
```

Run the agent with the query:
```bash
uv run python agent/agent.py "$QUERY"
```

The agent will print its reasoning, the tools it calls, and a final synthesised answer. Do not modify or summarise the output — display it as-is.
