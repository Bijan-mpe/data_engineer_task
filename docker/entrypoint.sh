#!/usr/bin/env sh
set -eu

echo "Running database migrations..."
alembic upgrade head

if [ "${RUN_PIPELINE_ON_STARTUP:-true}" = "true" ]; then
    echo "Running initial pipeline load..."
    python -m src.pipeline.pipeline
else
    echo "Skipping initial pipeline load because RUN_PIPELINE_ON_STARTUP is not true."
fi

echo "Starting API..."
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
