#!/bin/sh
# First boot: apply migrations and seed the sample inbox (both idempotent),
# then serve. Seeding is best-effort: without LLM keys it is skipped and the
# 30-second timer / POST /ingest/run picks the samples up later.
set -e

python -m app.bootstrap

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
