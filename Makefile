PY = .venv/bin/python

.PHONY: setup test demo lint

setup:            ## create venv, install deps, start postgres, run migrations
	uv venv -p 3.12 .venv
	uv pip install -p .venv -e ".[dev]"
	docker compose up -d db
	$(PY) -m app.bootstrap --migrate-only

test:             ## pytest with MockProvider, no keys needed
	$(PY) -m pytest -q

demo:             ## start the app at http://localhost:8000 (POST /ingest/run or the 30s timer seeds the samples; use LLM_PROVIDER_ORDER=mock for zero-key demo)
	$(PY) -m app.bootstrap --migrate-only
	$(PY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

lint:             ## ruff check
	$(PY) -m ruff check .
