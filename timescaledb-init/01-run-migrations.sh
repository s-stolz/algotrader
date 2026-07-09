#!/usr/bin/env bash
set -euo pipefail

exec python3 /usr/local/lib/algotrader/migrate_db.py \
    --in-container \
    --migrations-dir /docker-entrypoint-initdb.d/migrations
