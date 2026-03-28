.PHONY: install lint typecheck test test-unit test-integration test-eval check clean

install:
	uv pip install -e ".[agent,dev]"

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

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null; \
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null; \
	echo "Cleaned."
