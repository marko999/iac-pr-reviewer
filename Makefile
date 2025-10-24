.PHONY: install fmt lint test check

install:
pip install -e .[dev]

fmt:
black src tests
ruff check src tests --fix

lint:
ruff check src tests
black --check src tests

test:
pytest

check: fmt lint test
