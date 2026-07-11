#!/bin/sh
# Ingests whatever real documents are already in data/corpus/ (structured +
# regex, no AI call needed — never blocks on an LLM being configured), then
# starts the API. If data/corpus/ is empty, ingestion just does nothing and
# the API still starts — add documents live via the "Connect knowledge" tab
# or re-run `docker compose restart app` after dropping files in.
set -e
echo "==> Ingesting data/corpus (structured + regex, no AI)"
python scripts/ingest.py --structured-only || true
echo "==> Starting the API"
exec uvicorn brain.api.app:app --host 0.0.0.0 --port 8000
