#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Lint script for backtester
echo "🔍 Running Pylint on backtester..."
cd "$SCRIPT_DIR/backtester"
"$SCRIPT_DIR/.venv/bin/python" -m pylint src/ *.py --rcfile=.pylintrc

echo ""
echo "🔍 Running Pylint on database-accessor-api..."
cd "$SCRIPT_DIR/database-accessor-api"
"$SCRIPT_DIR/.venv/bin/python" -m pylint app/ *.py --rcfile=.pylintrc

echo ""
echo "🔍 Running Pylint on broker-service..."
cd "$SCRIPT_DIR/broker-service"
"$SCRIPT_DIR/.venv/bin/python" -m pylint app/ *.py --rcfile=.pylintrc

echo ""
echo "✅ Python linting complete!"
