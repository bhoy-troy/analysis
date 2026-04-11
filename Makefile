.PHONY: help install install-dev format lint type-check security-check test clean all

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  c        - Format code with black and isort"
	@echo "  make lint          - Run ruff linter"
	@echo "  make type-check    - Run mypy type checker"
	@echo "  make security-check- Run bandit security scanner"
	@echo "  make test          - Run pytest tests"
	@echo "  make all           - Run format, lint, type-check, and security-check"
	@echo "  make clean         - Remove cache and build artifacts"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt
	pre-commit install

format:
	@echo "Running black..."
	black .
	@echo "Running isort..."
	isort .
	@echo "✅ Code formatted!"

lint:
	@echo "Running ruff..."
	ruff check .
	@echo "✅ Linting complete!"

lint-fix:
	@echo "Running ruff with auto-fix..."
	ruff check --fix .
	@echo "✅ Linting complete!"

type-check:
	@echo "Running mypy..."
	mypy --install-types --non-interactive --ignore-missing-imports .
	@echo "✅ Type checking complete!"

security-check:
	@echo "Running bandit..."
	bandit -r . -f screen -x ./.venv,./venv,./build,./dist -ll
	@echo "Checking dependencies with safety..."
	safety check -r requirements.txt || true
	@echo "✅ Security check complete!"

test:
	@echo "Running pytest..."
	pytest -v
	@echo "✅ Tests complete!"

all: format lint type-check security-check
	@echo "✅ All checks passed!"

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Cleanup complete!"

run:
	streamlit run app.py

run-old:
	streamlit run app_cobh_analysis.py
