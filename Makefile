.PHONY: data notebook test lint

data:      ## скачать Online Retail II с Kaggle в data/raw/
	uv run python -m scripts.download

notebook:  ## выполнить ноутбук: графики в docs/, агрегаты для DataLens в data/datalens/
	cd notebooks && uv run jupyter nbconvert --execute --to notebook --inplace cohorts_ltv.ipynb

test:
	uv run pytest -q

lint:
	uv run ruff check .
	uv run ruff format --check .
