export PYTHONPATH := $(CURDIR)/src:$(PYTHONPATH)

.PHONY: clean lint format test test-gui tach

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info .tach
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	python3 -m ruff check .
	python3 -m mypy --strict src/oatbrain

format:
	python3 -m ruff format .

tach:
	.venv/bin/tach check

test:
	python3 -m pytest tests/unit

test-gui:
	GDK_BACKEND=x11 xvfb-run -a python3 -m pytest tests/gui
