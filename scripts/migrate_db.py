#!/usr/bin/env python3
"""Apply TimescaleDB migrations through the running Docker database container."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SHARED_ENV_PATH = ROOT_DIR / "config" / ".env.shared"
DB_SECRETS_ENV_PATH = ROOT_DIR / "config" / ".env.secrets.db"
MIGRATIONS_DIR = ROOT_DIR / "timescaledb-init" / "migrations"
CONTAINER_MIGRATIONS_DIR = "/docker-entrypoint-initdb.d/migrations"
MIGRATION_PATTERN = re.compile(r"^V(?P<version>\d{3})__(?P<name>[a-z0-9_]+)\.sql$")
NON_TRANSACTIONAL_MARKER = "-- migrate-db: no-transaction"
LEGACY_BASELINE_MAX_VERSION = 2
MIGRATION_ADVISORY_LOCK_ID = 824_973_244_147_976_327
LOCK_QUERY_COMPLETE_MARKER = "migration-lock-query-complete"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str

    @property
    def container_path(self) -> str:
        return f"{CONTAINER_MIGRATIONS_DIR}/{self.path.name}"

    @property
    def is_transactional(self) -> bool:
        return not self.path.read_text(encoding="utf-8").startswith(NON_TRANSACTIONAL_MARKER)


@dataclass
class MigrationLock:
    process: subprocess.Popen[str]


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SystemExit(f"Missing env file: {path}. Run `make config` first.")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"Invalid env line in {path}: {raw_line}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def load_migrations() -> list[Migration]:
    migrations: list[Migration] = []
    seen_versions: set[int] = set()

    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = MIGRATION_PATTERN.match(path.name)
        if not match:
            raise SystemExit(
                f"Malformed migration filename: {path.name}. "
                "Use VNNN__description.sql with lowercase snake_case names."
            )

        version = int(match.group("version"))
        if version in seen_versions:
            raise SystemExit(f"Duplicate migration version: V{version:03d}")
        seen_versions.add(version)

        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        migrations.append(
            Migration(
                version=version,
                name=match.group("name"),
                path=path,
                checksum=checksum,
            ),
        )

    if not migrations:
        raise SystemExit(f"No migrations found in {MIGRATIONS_DIR}")

    expected_versions = list(range(1, len(migrations) + 1))
    actual_versions = [migration.version for migration in migrations]
    if actual_versions != expected_versions:
        raise SystemExit(
            "Migration versions must be contiguous from V001. "
            f"Found: {', '.join(f'V{version:03d}' for version in actual_versions)}"
        )

    return migrations


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class Psql:
    def __init__(self, db_name: str, db_user: str) -> None:
        self.db_name = db_name
        self.db_user = db_user

    def command(self, *, capture: bool = False) -> list[str]:
        command = [
            "docker",
            "compose",
            "--env-file",
            "config/.env.shared",
            "exec",
            "-T",
            "timescaledb",
            "psql",
            "--username",
            self.db_user,
            "--dbname",
            self.db_name,
            "--set",
            "ON_ERROR_STOP=1",
        ]
        if capture:
            command.extend(["--tuples-only", "--no-align"])
        return command

    def run(self, sql: str, *, capture: bool = False) -> str:
        completed = subprocess.run(
            self.command(capture=capture),
            input=sql,
            text=True,
            capture_output=capture,
            cwd=ROOT_DIR,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() if capture else ""
            raise SystemExit(detail or f"psql failed with exit code {completed.returncode}")
        return completed.stdout.strip() if capture else ""


def create_ledger(psql: Psql) -> None:
    psql.run(
        """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum_sha256 CHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
""",
        capture=True,
    )


def _close_lock_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None and not process.stdin.closed:
        process.stdin.close()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)


def acquire_lock(psql: Psql) -> MigrationLock:
    process = subprocess.Popen(
        psql.command(capture=True),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=ROOT_DIR,
    )
    if process.stdin is None or process.stdout is None:
        _close_lock_process(process)
        raise SystemExit("Could not open a PostgreSQL session for the migration lock.")

    process.stdin.write(
        f"SELECT pg_try_advisory_lock({MIGRATION_ADVISORY_LOCK_ID});\n"
        f"\\echo {LOCK_QUERY_COMPLETE_MARKER}\n"
    )
    process.stdin.flush()

    output: list[str] = []
    for line in process.stdout:
        stripped = line.strip()
        if stripped == LOCK_QUERY_COMPLETE_MARKER:
            break
        if stripped:
            output.append(stripped)
    else:
        _close_lock_process(process)
        detail = "\n".join(output)
        raise SystemExit(detail or "The PostgreSQL migration lock session exited unexpectedly.")

    if not output or output[-1] != "t":
        _close_lock_process(process)
        raise SystemExit("Another database migration runner is already active.")
    return MigrationLock(process=process)


def release_lock(lock: MigrationLock) -> None:
    # Closing the client session releases the PostgreSQL advisory lock, including
    # when the runner exits unexpectedly and the pipe is closed by the OS.
    _close_lock_process(lock.process)


def read_applied(psql: Psql) -> dict[int, tuple[str, str]]:
    rows = psql.run(
        """
SELECT version, name, checksum_sha256
FROM schema_migrations
ORDER BY version;
""",
        capture=True,
    )
    applied: dict[int, tuple[str, str]] = {}
    if not rows:
        return applied

    for row in rows.splitlines():
        version_text, name, checksum = row.split("|", 2)
        applied[int(version_text)] = (name, checksum)
    return applied


def ensure_applied_files_exist(
    applied: dict[int, tuple[str, str]],
    migrations: list[Migration],
) -> None:
    versions = {migration.version for migration in migrations}
    missing = sorted(set(applied) - versions)
    if missing:
        formatted = ", ".join(f"V{version:03d}" for version in missing)
        raise SystemExit(f"Applied migrations are missing from disk: {formatted}")


def ensure_no_checksum_drift(
    applied: dict[int, tuple[str, str]],
    migrations: list[Migration],
) -> None:
    by_version = {migration.version: migration for migration in migrations}
    for version, (applied_name, applied_checksum) in sorted(applied.items()):
        migration = by_version[version]
        if migration.name != applied_name:
            raise SystemExit(
                f"Migration V{version:03d} was applied as {applied_name!r}, "
                f"but the file is now named {migration.name!r}."
            )
        if migration.checksum != applied_checksum:
            raise SystemExit(
                f"Checksum drift detected for V{version:03d}__{migration.name}. "
                "Add a new migration instead of editing an applied migration."
            )


def current_schema_matches_v002(psql: Psql) -> bool:
    result = psql.run(
        """
WITH checks AS (
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'markets'
          AND column_name = 'timezone'
    ) AS markets_timezone,
    EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'candles'
          AND column_name = 'timestamp_utc'
    ) AS candles_timestamp_utc,
    EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name IN ('backtest_runs', 'backtest_fills', 'backtest_closed_trades')
        HAVING COUNT(*) = 3
    ) AS backtest_tables,
    NOT EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('run_id'),
                ('trade_sequence'),
                ('trade_id'),
                ('symbol'),
                ('trade_direction'),
                ('quantity'),
                ('entry_timestamp_ms'),
                ('entry_price'),
                ('exit_timestamp_ms'),
                ('exit_price'),
                ('stop_loss_price'),
                ('take_profit_price'),
                ('realized_pnl'),
                ('fees'),
                ('exit_reason')
        ) AS required_columns(column_name)
        WHERE NOT EXISTS (
            SELECT 1
            FROM information_schema.columns existing_columns
            WHERE existing_columns.table_schema = 'public'
              AND existing_columns.table_name = 'backtest_closed_trades'
              AND existing_columns.column_name = required_columns.column_name
        )
    ) AS closed_trade_columns,
    EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'backtest_closed_trades'
          AND column_name = 'trade_direction'
          AND is_nullable = 'NO'
    ) AS trade_direction_required,
    EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'backtest_closed_trades_trade_direction_check'
          AND conrelid = to_regclass('public.backtest_closed_trades')
          AND contype = 'c'
          AND convalidated
          AND pg_get_constraintdef(oid) LIKE '%trade_direction%'
          AND pg_get_constraintdef(oid) LIKE '%long%'
          AND pg_get_constraintdef(oid) LIKE '%short%'
    ) AS trade_direction_check
)
SELECT markets_timezone
   AND candles_timestamp_utc
   AND backtest_tables
   AND closed_trade_columns
   AND trade_direction_required
   AND trade_direction_check
FROM checks;
""",
        capture=True,
    )
    return result == "t"


def baseline_existing_database(psql: Psql, migrations: list[Migration]) -> bool:
    if not current_schema_matches_v002(psql):
        return False

    # V003's policies and compression settings and V004's historical refresh
    # cannot be inferred reliably from the partial legacy catalog state. Replay
    # both migrations, as well as every future migration.
    baseline_migrations = [
        migration for migration in migrations if migration.version <= LEGACY_BASELINE_MAX_VERSION
    ]
    values = ",\n".join(
        (
            f"({migration.version}, {sql_literal(migration.name)}, "
            f"{sql_literal(migration.checksum)})"
        )
        for migration in baseline_migrations
    )
    psql.run(
        f"""
INSERT INTO schema_migrations (version, name, checksum_sha256)
VALUES
{values};
"""
    )
    print(f"Baselined {len(baseline_migrations)} existing migrations.", flush=True)
    return True


def apply_migration(psql: Psql, migration: Migration) -> None:
    print(f"Applying V{migration.version:03d}__{migration.name}.sql", flush=True)
    if migration.is_transactional:
        psql.run(
            f"""
BEGIN;
\\i {migration.container_path}
INSERT INTO schema_migrations (version, name, checksum_sha256)
VALUES (
    {migration.version},
    {sql_literal(migration.name)},
    {sql_literal(migration.checksum)}
);
COMMIT;
"""
        )
        return

    psql.run(
        f"""
\\i {migration.container_path}
INSERT INTO schema_migrations (version, name, checksum_sha256)
VALUES (
    {migration.version},
    {sql_literal(migration.name)},
    {sql_literal(migration.checksum)}
);
"""
    )


def apply_pending(
    psql: Psql,
    migrations: list[Migration],
    applied: dict[int, tuple[str, str]],
) -> None:
    pending = [migration for migration in migrations if migration.version not in applied]
    if not pending:
        print("Database migrations are already up to date.", flush=True)
        return

    expected_next = max(applied.keys(), default=0) + 1
    if pending[0].version != expected_next:
        raise SystemExit(f"Next migration must be V{expected_next:03d}.")

    for migration in pending:
        apply_migration(psql, migration)
    print(f"Applied {len(pending)} migration(s).", flush=True)


def main() -> int:
    migrations = load_migrations()
    shared_env = read_env_file(SHARED_ENV_PATH)
    read_env_file(DB_SECRETS_ENV_PATH)

    db_name = shared_env.get("TIMESCALEDB_DB") or "finance_data"
    db_user = shared_env.get("TIMESCALEDB_USER") or "postgres"
    psql = Psql(db_name=db_name, db_user=db_user)

    create_ledger(psql)
    lock = acquire_lock(psql)
    try:
        applied = read_applied(psql)
        ensure_applied_files_exist(applied, migrations)
        ensure_no_checksum_drift(applied, migrations)

        if not applied and baseline_existing_database(psql, migrations):
            applied = read_applied(psql)

        apply_pending(psql, migrations, applied)
    finally:
        release_lock(lock)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
