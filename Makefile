.PHONY: help install install-dev test format lint type-check clean

help:
	@echo "Available commands:"
	@echo "  install      Install production dependencies"
	@echo "  install-dev  Install development dependencies"
	@echo "  test         Run tests"
	@echo "  format       Format code with black"
	@echo "  lint         Run flake8 linter"
	@echo "  type-check   Run mypy type checker"
	@echo "  clean        Clean up cache files"

install:
	pip install -r requirements.txt
	pip install -e .

install-dev:
	pip install -r requirements-dev.txt
	pip install -e .

test:
	pytest

format:
	black src/ tests/ scripts/

lint:
	flake8 src/ tests/ scripts/

type-check:
	mypy src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage