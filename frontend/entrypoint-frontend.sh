#!/bin/sh
set -e

cd /app/frontend

checksum_file="node_modules/.algotrader-deps-checksum"

deps_checksum() {
  sha256sum package.json package-lock.json
}

if [ ! -d node_modules ] || [ ! -f "$checksum_file" ] || ! deps_checksum | cmp -s - "$checksum_file"; then
  echo "Installing frontend dependencies"
  npm ci --include=dev
  deps_checksum > "$checksum_file"
fi

if [ "$MODE" = "development" ]; then
  echo "Running in Development mode"
  npm run dev
else
  echo "Running in Production mode"
  npm run build
fi
