# /run-evals

Run the HN Pulse evaluation suite — validates that Claude picks the correct MCP tool for each natural language query.

## Usage

```
/run-evals [tier]
```

**Tiers (optional):**
- `/run-evals` — runs all three tiers: unit + integration + evals
- `/run-evals unit` — fast unit tests only (~0.3s, no API key needed)
- `/run-evals integration` — MCP server startup + tool schema tests (~4s, no API key)
- `/run-evals eval` — Claude tool-selection accuracy tests (~15s, requires `ANTHROPIC_API_KEY`)

---

## What this skill does

HN Pulse has a three-tier testing pyramid:

| Tier | Count | Cost | Speed | What it validates |
|------|-------|------|-------|-------------------|
| Unit | 29 | $0 | ~0.3s | Tool logic, HTTP mocking via pytest-httpx |
| Integration | 3 | $0 | ~4s | Real MCP server startup, all 8 tools registered with valid schemas |
| Eval | 10 | ~$0.002 | ~15s | Claude (haiku) selects the right tool for each natural language query |

Evals are the only tier that calls the Anthropic API and are skipped in CI by default.

---

## Steps

First, check that the package is installed:
```bash
uv run python -c "import hn_pulse" 2>/dev/null
```
If it fails, stop and print:
```
✗  hn_pulse package not found.
   Run:  uv pip install -e ".[agent,dev]"
```

Parse the optional tier argument from the input:
- If `unit` → run only unit tests
- If `integration` → run only integration tests
- If `eval` → check for API key first, then run only evals
- If no argument → run all tiers in sequence: unit first, then integration, then evals (if key present)

**If running evals or all tiers**, check that `ANTHROPIC_API_KEY` is set. If it is missing and the tier is `eval`, stop and print:
```
✗  ANTHROPIC_API_KEY is not set — eval tier requires the Anthropic API.
   Run:  export ANTHROPIC_API_KEY=your_key_here
   Or skip evals with:  /run-evals unit
```
If running all tiers and the key is missing, print a warning but still run unit and integration:
```
⚠  ANTHROPIC_API_KEY not set — skipping eval tier. Running unit + integration only.
```

Run the appropriate pytest command:

**Unit only:**
```bash
uv run pytest tests/ -m "not integration and not eval" -v --tb=short
```

**Integration only:**
```bash
uv run pytest tests/ -m "integration" -v --tb=short
```

**Eval only:**
```bash
uv run pytest tests/ -m "eval" -v --tb=short -s
```

**All tiers:**
```bash
uv run pytest tests/ -m "not eval" -v --tb=short
uv run pytest tests/ -m "eval" -v --tb=short -s
```

After each tier completes, print a one-line summary:
```
✓  Unit: 29 passed (0.31s)
✓  Integration: 3 passed (3.8s)
✓  Eval: 10 passed (14.2s)  [$0.002 API cost]
```

If any tier fails, print the pytest failure output in full and stop without running subsequent tiers.
