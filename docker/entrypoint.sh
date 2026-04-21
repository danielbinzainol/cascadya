#!/bin/sh
set -e

echo "Running DB migrations..."
alembic upgrade head

echo "Starting API..."
exec python -m uvicorn src.backoffice.api.main:app --host 0.0.0.0 --port 8000
