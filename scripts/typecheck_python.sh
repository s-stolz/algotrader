#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIGS=(
  "pyrightconfig.json"
  "backtester/pyrightconfig.json"
  "broker-service/pyrightconfig.json"
  "database-accessor-api/pyrightconfig.json"
  "indicator-api/pyrightconfig.json"
  "ingestion-service/pyrightconfig.json"
  "webserver/pyrightconfig.json"
)

if [[ -x "${REPO_ROOT}/.venv/bin/pyright" ]]; then
  PYRIGHT_CMD=("${REPO_ROOT}/.venv/bin/pyright")
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]] \
  && "${REPO_ROOT}/.venv/bin/python" -m pyright --version >/dev/null 2>&1; then
  PYRIGHT_CMD=("${REPO_ROOT}/.venv/bin/python" -m pyright)
elif command -v pyright >/dev/null 2>&1; then
  PYRIGHT_CMD=(pyright)
else
  echo "Pyright is not installed. Run: make venv-root" >&2
  exit 127
fi

for config in "${CONFIGS[@]}"; do
  echo "==> Pyright ${config}"
  "${PYRIGHT_CMD[@]}" -p "${REPO_ROOT}/${config}"
done
