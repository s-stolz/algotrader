#!/bin/bash

# Lint script for backtester
echo "🔍 Running Pylint on backtester..."
cd /Users/basti/Documents/Programming/algotrader/backtester
/Users/basti/Documents/Programming/algotrader/.venv/bin/python -m pylint src/ *.py --rcfile=.pylintrc

echo ""
echo "🔍 Running Pylint on database-accessor-api..."
cd /Users/basti/Documents/Programming/algotrader/database-accessor-api
/Users/basti/Documents/Programming/algotrader/.venv/bin/python -m pylint app/ *.py --rcfile=.pylintrc

echo ""
echo "✅ Python linting complete!"
