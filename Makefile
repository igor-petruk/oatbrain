export PYTHONPATH := $(CURDIR)/src:$(PYTHONPATH)

.PHONY: clean lint test

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info .tach
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	python3 -m ruff check .
	python3 -m mypy --strict src/oatbrain
	python3 -m tach check

test:
	python3 -m pytest tests/unit
