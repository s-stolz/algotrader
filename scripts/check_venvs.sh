#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVICES=(
  "broker-service"
  "indicator-api"
  "database-accessor-api"
  "ingestion-service"
  "webserver"
  "backtester"
)

usage() {
  cat <<'EOF'
Usage:
  ./scripts/check_venvs.sh all
  ./scripts/check_venvs.sh <service> [<service> ...]
EOF
}

contains_service() {
  local candidate="$1"
  local service
  for service in "${SERVICES[@]}"; do
    if [[ "${service}" == "${candidate}" ]]; then
      return 0
    fi
  done
  return 1
}

check_service() {
  local service="$1"
  local service_dir="${REPO_ROOT}/${service}"
  local venv_python="${service_dir}/.venv/bin/python"

  if [[ ! -x "${venv_python}" ]]; then
    echo "Missing venv interpreter for ${service}: ${venv_python}" >&2
    return 1
  fi

  echo "==> Checking ${service}"
  "${venv_python}" -m pip check
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

targets=()
if [[ "$1" == "all" ]]; then
  targets=("${SERVICES[@]}")
else
  for target in "$@"; do
    if ! contains_service "${target}"; then
      echo "Unknown service: ${target}" >&2
      echo "Valid services: ${SERVICES[*]}" >&2
      exit 1
    fi
    targets+=("${target}")
  done
fi

for service in "${targets[@]}"; do
  check_service "${service}"
done

echo "All requested environments passed pip checks."
