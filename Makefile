export PYTHONPATH := $(CURDIR)/src:$(PYTHONPATH)

.PHONY: clean lint format test test-gui tach

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info .tach
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	.venv/bin/python3 -m ruff check .
	.venv/bin/python3 -m mypy --strict src/oatbrain

format:
	.venv/bin/python3 -m ruff format .

tach:
	.venv/bin/tach check

test:
	xvfb-run -a .venv/bin/python3 -m pytest tests/unit

test-gui:
	xvfb-run -a .venv/bin/python3 -m pytest tests/gui
