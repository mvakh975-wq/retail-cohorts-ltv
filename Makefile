.PHONY: data notebook test lint

data:
	uv run python -m scripts.download

notebook:
	cd notebooks && uv run jupyter nbconvert --execute --to notebook --inplace cohorts_ltv.ipynb

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
