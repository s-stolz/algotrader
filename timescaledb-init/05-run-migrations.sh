#!/bin/sh
# Fresh volumes run this after legacy bootstrap; existing volumes execute it explicitly.
set -eu
export LC_ALL=C
migration_dir="${MIGRATIONS_DIR:-/docker-entrypoint-initdb.d/migrations}"
snapshot_dir=$(mktemp -d)
trap 'rm -rf "$snapshot_dir"' 0
trap 'exit 1' 1 2 15

previous_version=0
for migration in "$migration_dir"/*.sql; do
    [ -f "$migration" ] || continue
    name=$(basename "$migration")
    if ! printf '%s\n' "$name" | grep -Eq '^V[0-9]{3}__[a-z0-9_]+\.sql$'; then
        printf 'Invalid migration filename: %s\n' "$name" >&2
        exit 1
    fi
    version=$(printf '%s\n' "$name" | awk '{ print substr($0, 2, 3) + 0 }')
    if [ "$version" -ne "$((previous_version + 1))" ]; then
        printf 'Migration versions must be unique and consecutive from V001: %s\n' "$name" >&2
        exit 1
    fi
    # Hash and execute one immutable snapshot, even if deployment files change.
    cp "$migration" "$snapshot_dir/$name"
    checksum=$(sha256sum "$snapshot_dir/$name" | cut -d ' ' -f 1)
    printf '%s %s %s\n' "$version" "$name" "$checksum" >> "$snapshot_dir/inventory"
    previous_version=$version
done
if [ "$previous_version" -eq 0 ]; then
    printf 'No migrations found in %s\n' "$migration_dir" >&2
    exit 1
fi

{
    cat <<'SQL'
SELECT pg_advisory_lock(824973244147976327);
BEGIN;
CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TEMP TABLE migration_inventory (
    version INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, checksum TEXT NOT NULL
) ON COMMIT PRESERVE ROWS;
SQL
    while read -r version name checksum; do
        printf "INSERT INTO migration_inventory VALUES (%s, '%s', '%s');\n" \
            "$version" "$name" "$checksum"
    done < "$snapshot_dir/inventory"
    cat <<'SQL'
DO $$ BEGIN
    IF EXISTS (
        SELECT FROM schema_migrations applied
        LEFT JOIN migration_inventory inventory USING (name)
        WHERE inventory.name IS NULL
    ) THEN
        RAISE EXCEPTION 'Applied migration missing from inventory';
    END IF;
    IF EXISTS (
        SELECT FROM schema_migrations applied
        JOIN migration_inventory inventory USING (name)
        WHERE applied.checksum <> inventory.checksum
    ) THEN
        RAISE EXCEPTION 'Applied migration checksum mismatch';
    END IF;
    IF EXISTS (
        SELECT FROM schema_migrations applied
        JOIN migration_inventory inventory USING (name)
        WHERE inventory.version > (SELECT count(*) FROM schema_migrations)
    ) THEN
        RAISE EXCEPTION 'Applied migration versions must form a consecutive prefix';
    END IF;
END $$;
COMMIT;
SQL
    while read -r version name checksum; do
        cat <<SQL
BEGIN;
SELECT NOT EXISTS (SELECT FROM schema_migrations WHERE name = '$name') AS apply_migration \gset
\if :apply_migration
SQL
        cat "$snapshot_dir/$name"
        cat <<SQL

INSERT INTO schema_migrations(name, checksum) VALUES ('$name', '$checksum');
\endif
COMMIT;
SQL
    done < "$snapshot_dir/inventory"
    printf 'SELECT pg_advisory_unlock(824973244147976327);\n'
} > "$snapshot_dir/run.sql"
psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" \
    --dbname "${TIMESCALEDB_DB:-finance_data}" --file "$snapshot_dir/run.sql"
