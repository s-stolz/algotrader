#!/bin/sh
if [ "$MODE" = "development" ]; then
  echo "Running in Development mode"
  cd /app/frontend    # Required for hot reload
  npm run dev
else
  echo "Running in Production mode"
  npm run build
fi
