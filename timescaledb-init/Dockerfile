FROM timescale/timescaledb:latest-pg17

RUN apk add --no-cache python3

COPY scripts/migrate_db.py /usr/local/lib/algotrader/migrate_db.py
COPY timescaledb-init/ /docker-entrypoint-initdb.d/
