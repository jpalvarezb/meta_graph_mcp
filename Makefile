.PHONY: lint format test build clean check help

PYTHON := python
PYTEST := pytest
RUFF := ruff
BLACK := black
MYPY := mypy
DOCKER := docker

help:  ## Show this help menu
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

lint:  ## Run linting checks (ruff)
	$(RUFF) check src tests

format:  ## Run code formatting (black)
	$(BLACK) src tests

check: lint format ## Run all code quality checks (lint, format, mypy)
	$(MYPY) src tests

test:  ## Run tests with coverage
	$(PYTEST) --cov=meta_mcp --cov-report=term-missing --cov=mcp_meta_sdk

build:  ## Build Docker image
	$(DOCKER) build -t meta-mcp:latest -f docker/Dockerfile .

clean:  ## Clean up build artifacts and cache
	rm -rf dist/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
