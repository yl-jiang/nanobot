# Makefile for nanobot
# Usage: make <target>

# Python interpreter (use virtual environment)
PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help agent gateway onboard status sync install dev test lint clean

# Default target
help:
	@echo "nanobot commands:"
	@echo "  make agent       - Start interactive agent"
	@echo "  make gateway     - Start gateway server"
	@echo "  make onboard     - Initialize nanobot configuration"
	@echo "  make status      - Show nanobot status"
	@echo "  make channels    - Show channel status"
	@echo "  make cron        - List cron jobs"
	@echo ""
	@echo "Development:"
	@echo "  make sync        - Create venv and install dependencies via uv"
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Install in development mode"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linter"
	@echo "  make clean       - Clean build artifacts"

# Extra arguments (e.g., make agent ARGS="--logs")
ARGS :=

# ============================================================================
# Core Commands
# ============================================================================

agent:
	$(PYTHON) -m nanobot.cli.commands agent $(ARGS)

gateway:
	caffeinate -s $(PYTHON) -m nanobot.cli.commands gateway $(ARGS)

onboard:
	$(PYTHON) -m nanobot.cli.commands onboard

status:
	$(PYTHON) -m nanobot.cli.commands status

channels:
	$(PYTHON) -m nanobot.cli.commands channels status

cron:
	$(PYTHON) -m nanobot.cli.commands cron list

# ============================================================================
# Development
# ============================================================================

sync:
	uv venv .venv
	uv sync

install:
	$(PIP) install -r requirements.txt

dev:
	$(PIP) install -e .

test:
	pytest tests/ -v

lint:
	ruff check nanobot/

format:
	ruff format nanobot/

clean:
	rm -rf build/ dist/ *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
