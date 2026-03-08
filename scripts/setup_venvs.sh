#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
SHARED_CONSTRAINTS="${REPO_ROOT}/constraints-shared.txt"

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
  ./scripts/setup_venvs.sh [--recreate] all
  ./scripts/setup_venvs.sh [--recreate] <service> [<service> ...]

Examples:
  ./scripts/setup_venvs.sh all
  ./scripts/setup_venvs.sh broker-service webserver
  ./scripts/setup_venvs.sh --recreate all
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

install_service() {
  local service="$1"
  local service_dir="${REPO_ROOT}/${service}"
  local venv_dir="${service_dir}/.venv"
  local python_in_venv="${venv_dir}/bin/python"
  local requirements_file="${service_dir}/requirements.txt"
  local override_file="${service_dir}/constraints.override.txt"

  if [[ ! -f "${requirements_file}" ]]; then
    echo "Missing requirements file: ${requirements_file}" >&2
    return 1
  fi

  if [[ "${RECREATE}" == "1" && -d "${venv_dir}" ]]; then
    rm -rf "${venv_dir}"
  fi

  if [[ ! -d "${venv_dir}" ]]; then
    "${PYTHON_BIN}" -m venv "${venv_dir}"
  fi

  if ! "${python_in_venv}" -m pip install --upgrade pip setuptools wheel; then
    echo "Warning: failed to upgrade pip/setuptools/wheel for ${service}; continuing." >&2
  fi
  (
    cd "${service_dir}"
    "${python_in_venv}" -m pip install -c "${SHARED_CONSTRAINTS}" -r "requirements.txt"
  )

  if [[ -f "${override_file}" ]]; then
    (
      cd "${service_dir}"
      "${python_in_venv}" -m pip install -r "constraints.override.txt"
    )
  fi
}

RECREATE=0
if [[ "${1:-}" == "--recreate" ]]; then
  RECREATE=1
  shift
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if [[ ! -f "${SHARED_CONSTRAINTS}" ]]; then
  echo "Missing shared constraints: ${SHARED_CONSTRAINTS}" >&2
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
  echo "==> Setting up ${service}"
  install_service "${service}"
done

echo "All requested environments are ready."
