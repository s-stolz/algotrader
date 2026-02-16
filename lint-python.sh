#!/bin/bash

set -euo pipefail

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -x "$SCRIPT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if command -v ruff >/dev/null 2>&1; then
  RUFF_CMD=(ruff)
else
  RUFF_CMD=("$PYTHON_BIN" -m ruff)
fi

if command -v black >/dev/null 2>&1; then
  BLACK_CMD=(black)
else
  BLACK_CMD=("$PYTHON_BIN" -m black)
fi

SERVICES=(
  "backtester"
  "broker-service"
  "database-accessor-api"
  "indicator-api"
  "ingestion-service"
  "webserver"
)

echo "🔍 Running Ruff checks..."
cd "$SCRIPT_DIR"
for service in "${SERVICES[@]}"; do
  echo "  - $service"
  "${RUFF_CMD[@]}" check "$service"
done

echo ""
echo "🔍 Running Black checks..."
for service in "${SERVICES[@]}"; do
  echo "  - $service"
  "${BLACK_CMD[@]}" --check "$service"
done

echo ""
echo "✅ Python linting and formatting checks complete!"
