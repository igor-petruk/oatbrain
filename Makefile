.PHONY: clean lint test

clean:
	rm -rf .pytest_cache .ruff_cache build dist *.egg-info .tach
	find . -type d -name __pycache__ -exec rm -rf {} +

lint:
	ruff check .
	mypy --strict src/oatbrain
	tach check

test:
	pytest tests/unit
