#!/usr/bin/env bash
# set -x  # echo all commands
./wait-for-it.sh timescaledb:5432 --timeout=30 --strict -- echo "TimescaleDB is up"

pid=0

# SIGTERM-handler
term_handler() {
  echo "term_handler"
  if [ $pid -ne 0 ]; then
    kill -SIGTERM "$pid"
    wait "$pid"
  fi
  exit 143; # 128 + 15 -- SIGTERM
}

if [ "$MODE" = "development" ]; then
  echo "Running in Development mode"
  npx nodemon server.js
else
  echo "Running in Production mode"
  # setup handlers
  # on callback, kill the last background process, which is `tail -f /dev/null` and execute the specified handler
  trap 'kill ${!}; term_handler' SIGTERM

  # run application
  node server.js &
  pid="$!"

  # wait forever
  while true
  do
    tail -f /dev/null & wait ${!}
  done
fi
