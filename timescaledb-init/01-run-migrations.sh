#!/usr/bin/env bash
set -euo pipefail

db_name="${TIMESCALEDB_DB:-finance_data}"
db_user="${TIMESCALEDB_USER:-${POSTGRES_USER:-postgres}}"
migrations_dir="/docker-entrypoint-initdb.d/migrations"

psql --username "$db_user" --dbname "$db_name" --set ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum_sha256 CHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

for migration_path in "$migrations_dir"/V*__*.sql; do
    [ -e "$migration_path" ] || continue

    migration_file="$(basename "$migration_path")"
    version="${migration_file%%__*}"
    version="${version#V}"
    name="${migration_file#*__}"
    name="${name%.sql}"
    checksum="$(sha256sum "$migration_path" | awk '{print $1}')"

    if head -n 1 "$migration_path" | grep -qx -- "-- migrate-db: no-transaction"; then
        psql \
            --username "$db_user" \
            --dbname "$db_name" \
            --set ON_ERROR_STOP=1 \
            --set "migration_version=$version" \
            --set "migration_name=$name" \
            --set "migration_checksum=$checksum" <<SQL
\\i $migration_path
INSERT INTO schema_migrations (version, name, checksum_sha256)
VALUES (
    :migration_version,
    :'migration_name',
    :'migration_checksum'
);
SQL
    else
        psql \
            --username "$db_user" \
            --dbname "$db_name" \
            --set ON_ERROR_STOP=1 \
            --set "migration_version=$version" \
            --set "migration_name=$name" \
            --set "migration_checksum=$checksum" <<SQL
BEGIN;
\\i $migration_path
INSERT INTO schema_migrations (version, name, checksum_sha256)
VALUES (
    :migration_version,
    :'migration_name',
    :'migration_checksum'
);
COMMIT;
SQL
    fi
done
