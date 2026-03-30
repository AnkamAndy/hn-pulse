.PHONY: install install-temporal lint typecheck test test-unit test-integration test-eval check clean \
        temporal-dev temporal-worker temporal-research temporal-digest temporal-monitor

install:
	uv pip install -e ".[agent,dev]"

install-temporal:
	uv pip install -e ".[temporal]"

lint:
	uv run ruff check src/ tests/

typecheck:
	uv run mypy src/

test-unit:
	uv run pytest tests/unit/ -v --tb=short

test-integration:
	uv run pytest -m integration -v --tb=short

test-eval:
	uv run pytest -m eval -v -s

test:
	uv run pytest -m "not eval" -v --tb=short

check: lint typecheck test

temporal-dev:
	temporal server start-dev --ui-port 8233

temporal-worker:
	uv run python temporal/worker.py

temporal-research:
	uv run python temporal/run_workflow.py research "$(QUERY)"

temporal-digest:
	mkdir -p output && uv run python temporal/run_workflow.py digest --output output/

temporal-monitor:
	uv run python temporal/run_workflow.py monitor "$(TOPIC)" --days $(or $(DAYS),7)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null; \
	echo "Cleaned."
