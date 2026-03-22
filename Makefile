# Makefile for nanobot

.PHONY: onboard gateway agent chat status channels-status channels-login test lint format clean install-dev help

# Use uv run if available, otherwise fallback to python
PYTHON := $(shell if command -v uv > /dev/null; then echo "uv run python"; else echo "python"; fi)
PIP := $(shell if command -v uv > /dev/null; then echo "uv pip"; else echo "pip"; fi)

help:
	@echo "Available commands:"
	@echo "  make onboard          - Initialize nanobot configuration and workspace"
	@echo "  make gateway          - Start the nanobot gateway (port 18790)"
	@echo "  make agent            - Start the agent in interactive mode"
	@echo "  make chat             - Start the agent in interactive mode with logs enabled"
	@echo "  make status           - Show nanobot and provider status"
	@echo "  make channels-status  - Show status of all communication channels"
	@echo "  make channels-login   - Link device (WhatsApp/Mochat) via QR code"
	@echo "  make install-dev      - Install development dependencies"
	@echo "  make test             - Run tests"
	@echo "  make lint             - Run linting checks"
	@echo "  make format           - Format code using ruff"
	@echo "  make clean            - Remove cache files and build artifacts"

# CLI Commands
onboard:
	$(PYTHON) -m nanobot onboard

gateway:
	$(PYTHON) -m nanobot gateway

agent:
	$(PYTHON) -m nanobot agent

chat:
	$(PYTHON) -m nanobot agent --logs

status:
	$(PYTHON) -m nanobot status

channels-status:
	$(PYTHON) -m nanobot channels status

channels-login:
	$(PYTHON) -m nanobot channels login

# Dev Commands
install-dev:
	if command -v uv > /dev/null; then \
		uv sync --extra dev --extra matrix; \
	else \
		$(PIP) install -e ".[dev,matrix]"; \
	fi

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info
