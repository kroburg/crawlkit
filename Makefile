# CI calls these same targets, so the two cannot drift apart.

VENV    ?= .venv
PY      ?= $(VENV)/bin/python
PYTEST  ?= $(VENV)/bin/pytest
RUFF    ?= $(VENV)/bin/ruff
NOT_OPTIONAL := not chrome and not live and not corpus

.PHONY: help venv install install-bare test test-bare test-node test-chrome examples lint fmt check fixture clean

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/' | expand -t22

venv: ## create the virtualenv
	python3 -m venv $(VENV)

install: venv ## install with every optional dependency
	$(VENV)/bin/pip install -q -e '.[dev]'
	$(PY) -m playwright install chromium

install-bare: venv ## install with no extras, to prove the pure layer is pure
	$(VENV)/bin/pip install -q -e .

test: ## the default suite
	$(PYTEST) -q -m "$(NOT_OPTIONAL)"

test-bare: ## the suite on an interpreter without playwright or pillow
	$(PYTEST) -q -m "not playwright and $(NOT_OPTIONAL)"

test-node: ## the node suite
	cd node && npm --silent ci && node --test test/*.test.js

test-chrome: ## the node suite including the tests that need real Chrome
	cd node && node --test test/*.test.js

examples: ## every documented example, against the local fixture server
	$(PYTEST) -q tests/test_examples.py

lint: ## style and the two publishability guards
	$(RUFF) check .
	$(RUFF) format --check .
	$(PYTEST) -q tests/test_no_private_references.py tests/test_console_scripts.py

fmt: ## apply formatting
	$(RUFF) format .
	$(RUFF) check --fix .

check: lint test test-node examples ## everything that gates a release

fixture: ## run the local target by hand, to poke at it
	$(PY) -m fixtures.server --port 8080

clean:
	rm -rf .pytest_cache .cache **/__pycache__ crawlkit.egg-info
