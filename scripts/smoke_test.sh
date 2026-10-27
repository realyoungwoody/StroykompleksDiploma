#!/bin/sh
set -eu
BASE_URL="${BASE_URL:-http://localhost:8080}"
curl -fsS "$BASE_URL/api/v1/health"
curl -fsS "$BASE_URL/api/v1/services"
curl -fsS "$BASE_URL/api/docs" >/dev/null
echo "Smoke test: PASS"

