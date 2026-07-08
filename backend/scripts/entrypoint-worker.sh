#!/usr/bin/env bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-nltoregex.settings.local}"

if ! command -v java >/dev/null 2>&1; then
  echo "Java runtime not found — Spark tasks will fail." >&2
  exit 1
fi

echo "Using JAVA_HOME=${JAVA_HOME:-unset} ($(java -version 2>&1 | head -1))"

exec uv run celery -A nltoregex worker \
  -l "${CELERY_LOG_LEVEL:-info}" \
  --pool="${CELERY_WORKER_POOL:-solo}"
