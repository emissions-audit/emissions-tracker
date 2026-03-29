#!/bin/bash
set -euo pipefail

COMPOSE="docker compose"
API_URL="http://localhost:8000"

cleanup() {
    echo ""
    echo "=== Tearing down ==="
    $COMPOSE down -v 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Building images ==="
$COMPOSE build

echo "=== Starting database ==="
$COMPOSE up -d db

echo "=== Waiting for database ==="
for i in $(seq 1 30); do
    if $COMPOSE exec -T db pg_isready -U emissions > /dev/null 2>&1; then
        echo "Database ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Database not ready after 30s"
        exit 1
    fi
    sleep 1
done

echo "=== Running migrations ==="
$COMPOSE run --rm --entrypoint alembic pipeline upgrade head

echo "=== Starting API ==="
$COMPOSE up -d api

echo "=== Waiting for API ==="
for i in $(seq 1 30); do
    if curl -sf "$API_URL/v1/stats" > /dev/null 2>&1; then
        echo "API ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: API not ready after 30s"
        $COMPOSE logs api
        exit 1
    fi
    sleep 1
done

echo "=== Seeding data ==="
$COMPOSE run --rm --entrypoint emissions-pipeline pipeline seed

echo ""
echo "=== Running E2E tests ==="
python -m pytest tests/e2e/ -v --tb=short

echo ""
echo "=== All E2E tests passed ==="
