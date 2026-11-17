#!/usr/bin/env bash
set -euo pipefail

bundle_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command_name=setup
installation_dir=""
upgrade_option=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    setup|start|stop|status|reconnect|upgrade) command_name="$1"; shift ;;
    --directory) installation_dir="${2:?--directory requires a path}"; shift 2 ;;
    --prerelease|--from-bundle)
      [[ -z "$upgrade_option" ]] || { echo "Choose one upgrade option." >&2; exit 2; }
      upgrade_option="$1"; shift ;;
    *) echo "Usage: $0 [setup|start|stop|status|reconnect|upgrade] [--directory PATH] [--prerelease|--from-bundle]" >&2; exit 2 ;;
  esac
done
if [[ -n "$upgrade_option" && "$command_name" != upgrade ]]; then
  echo "$upgrade_option requires the upgrade command." >&2; exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Install Docker with Compose: https://docs.docker.com/get-started/get-docker/" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Start Docker Desktop or your Docker engine, then retry." >&2
  exit 1
fi
engine_os="$(docker info --format '{{.OSType}}')"
if [[ "$engine_os" != linux ]]; then
  echo "Select Linux containers in Docker Desktop, then retry." >&2; exit 1
fi
endpoint="${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}"
case "$endpoint" in unix://*) ;; *)
  echo "Use a local Docker engine with a Unix socket for this local installation." >&2; exit 1 ;;
esac
compose_version="$(docker compose version --short 2>/dev/null)" || {
  echo "Install Docker Compose: https://docs.docker.com/compose/install/" >&2; exit 1;
}
compose_version="${compose_version#v}"
IFS=. read -r compose_major compose_minor _ <<< "$compose_version"
if [[ "$compose_major" -lt 2 || ( "$compose_major" -eq 2 && "$compose_minor" -lt 30 ) ]]; then
  echo "Docker Compose 2.30 or newer is required: https://docs.docker.com/compose/install/" >&2
  exit 1
fi
case "$(uname -s)" in
  Darwin)
    default_dir="$HOME/Library/Application Support/AlgoTrader"
    config_dir="$default_dir/config"; data_dir="$default_dir/data"; state_dir="$default_dir/state"
    socket_source=/var/run/docker.sock
    ;;
  Linux)
    config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/algotrader"
    data_dir="${XDG_DATA_HOME:-$HOME/.local/share}/algotrader"
    state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/algotrader"
    endpoint="${DOCKER_HOST:-$(docker context inspect --format '{{.Endpoints.docker.Host}}')}"
    case "$endpoint" in unix://*) socket_source="${endpoint#unix://}" ;; *)
      echo "Use a local Docker engine with a Unix socket for this local installation." >&2; exit 1 ;;
    esac
    ;;
  *) echo "Use algotrader.ps1 on Windows." >&2; exit 1 ;;
esac
if [[ -z "$installation_dir" && "$command_name" == setup && ! -f "$state_dir/installation.json" && -t 0 ]]; then
  echo "Configuration: $config_dir"
  echo "Release files: $data_dir"
  echo "State and backups: $state_dir"
  read -r -p "Alternative installation directory (Enter keeps these defaults): " installation_dir
fi
if [[ -n "$installation_dir" ]]; then
  mkdir -p "$installation_dir"
  installation_dir="$(cd "$installation_dir" && pwd)"
  config_dir="$installation_dir/config"; data_dir="$installation_dir/data"; state_dir="$installation_dir/state"
fi
umask 077
mkdir -p "$config_dir" "$data_dir" "$state_dir"
if [[ "$command_name" != setup && "$upgrade_option" != --from-bundle && -f "$state_dir/installation.json" ]]; then
  # The controller writes the accepted version as a top-level, two-space-indented JSON field.
  installed="$(sed -nE 's/^  "version": "(v[0-9A-Za-z.-]+)",?$/\1/p' "$state_dir/installation.json")"
  if [[ "$installed" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ && -f "$data_dir/releases/$installed/installer-image.txt" ]]; then
    bundle_dir="$data_dir/releases/$installed"
  fi
fi
if [[ ! -f "$bundle_dir/installer-image.txt" || ! -f "$bundle_dir/release.json" ]]; then
  echo "Download and extract a complete AlgoTrader release ZIP first." >&2
  exit 1
fi
IFS= read -r installer_image < "$bundle_dir/installer-image.txt"
if [[ ! "$installer_image" =~ ^ghcr\.io/[a-z0-9./_-]+@sha256:[0-9a-f]{64}$ ]]; then
  echo "Invalid installer image in release bundle." >&2; exit 1
fi
controller_name="algotrader-setup-$$-$RANDOM"
interactive=(--interactive)
[[ ! -t 0 ]] || interactive+=(--tty)
args=(run --rm "${interactive[@]}" --name "$controller_name"
  --volume "$socket_source:/var/run/docker.sock"
  --volume "$config_dir:/config" --volume "$data_dir:/data" --volume "$state_dir:/state"
  --volume "$bundle_dir:/bundle:ro"
  --env "ALGOTRADER_CONTROLLER_NAME=$controller_name"
  --env "ALGOTRADER_INSTALLER_IMAGE=$installer_image"
  --env "ALGOTRADER_HOST_UID=$(id -u)" --env "ALGOTRADER_HOST_GID=$(id -g)")
echo "Configuration: $config_dir"
echo "State and backups: $state_dir"
if [[ "$command_name" == upgrade ]]; then
  if [[ "$upgrade_option" == --from-bundle ]]; then
    exec docker "${args[@]}" "$installer_image" apply-bundle
  elif [[ "$upgrade_option" == --prerelease ]]; then
    exec docker "${args[@]}" "$installer_image" update --prerelease
  fi
  exec docker "${args[@]}" "$installer_image" update
fi
exec docker "${args[@]}" "$installer_image" "$command_name"
