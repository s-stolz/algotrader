from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from contextlib import ExitStack
from io import StringIO
from pathlib import Path
from unittest import mock

import scripts.migrate_db as migrate_db


def migration(version: int) -> migrate_db.Migration:
    return migrate_db.Migration(
        version=version,
        name=f"migration_{version}",
        path=Path(f"V{version:03d}__migration_{version}.sql"),
        checksum=f"checksum-{version}",
        sql="SELECT 1;\n",
    )


class RecordingPsql(migrate_db.Psql):
    def __init__(self, results: list[str] | None = None) -> None:
        self.results = iter(results or [])
        self.calls: list[tuple[str, bool]] = []

    def run(self, sql: str, *, capture: bool = False) -> str:
        self.calls.append((sql, capture))
        return next(self.results, "")


class MigrationLoadingTests(unittest.TestCase):
    def test_load_migrations_requires_contiguous_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            migrations_dir = Path(temp_dir)
            (migrations_dir / "V001__base_schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
            (migrations_dir / "V003__skip.sql").write_text("SELECT 1;\n", encoding="utf-8")

            with mock.patch.object(migrate_db, "MIGRATIONS_DIR", migrations_dir):
                with self.assertRaises(SystemExit) as context:
                    migrate_db.load_migrations()

            self.assertIn("contiguous", str(context.exception))

    def test_load_migrations_rejects_malformed_names(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            migrations_dir = Path(temp_dir)
            (migrations_dir / "001_bad.sql").write_text("SELECT 1;\n", encoding="utf-8")

            with mock.patch.object(migrate_db, "MIGRATIONS_DIR", migrations_dir):
                with self.assertRaises(SystemExit) as context:
                    migrate_db.load_migrations()

            self.assertIn("Malformed migration filename", str(context.exception))

    def test_load_migrations_calculates_checksums(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            migrations_dir = Path(temp_dir)
            (migrations_dir / "V001__base_schema.sql").write_text("SELECT 1;\n", encoding="utf-8")

            with mock.patch.object(migrate_db, "MIGRATIONS_DIR", migrations_dir):
                migrations = migrate_db.load_migrations()

            self.assertEqual(len(migrations), 1)
            self.assertEqual(migrations[0].version, 1)
            self.assertEqual(migrations[0].name, "base_schema")
            self.assertEqual(
                migrations[0].checksum,
                "b4e0497804e46e0a0b0b8c31975b062152d551bac49c3c2e80932567b4085dcd",
            )


class PsqlTransportTests(unittest.TestCase):
    def test_in_container_transport_calls_psql_directly(self):
        psql = migrate_db.Psql(db_name="trading", db_user="runner", in_container=True)

        self.assertEqual(
            psql.command(capture=True),
            [
                "psql",
                "--username",
                "runner",
                "--dbname",
                "trading",
                "--set",
                "ON_ERROR_STOP=1",
                "--tuples-only",
                "--no-align",
            ],
        )

    def test_in_container_cli_uses_database_environment_and_requested_migrations(self):
        migrations = [migration(1)]
        psql = mock.Mock()
        migrations_dir = Path("/docker-entrypoint-initdb.d/migrations")

        with ExitStack() as stack:
            load = stack.enter_context(
                mock.patch.object(migrate_db, "load_migrations", return_value=migrations)
            )
            psql_type = stack.enter_context(
                mock.patch.object(migrate_db, "Psql", return_value=psql)
            )
            run_migrations = stack.enter_context(mock.patch.object(migrate_db, "run_migrations"))
            result = migrate_db.main(
                ["--in-container", "--migrations-dir", str(migrations_dir)],
                environ={
                    "TIMESCALEDB_DB": "trading",
                    "TIMESCALEDB_USER": "runner",
                },
            )

        self.assertEqual(result, 0)
        load.assert_called_once_with(migrations_dir)
        psql_type.assert_called_once_with(
            db_name="trading",
            db_user="runner",
            in_container=True,
        )
        run_migrations.assert_called_once_with(psql, migrations)

    def test_in_container_cli_requires_generated_database_environment(self):
        with self.assertRaisesRegex(SystemExit, "Missing database configuration"):
            migrate_db.main(["--in-container"], environ={})


class BootstrapEntrypointTests(unittest.TestCase):
    def test_bootstrap_delegates_to_the_canonical_runner(self):
        entrypoint = migrate_db.ROOT_DIR / "timescaledb-init" / "01-run-migrations.sh"

        with tempfile.TemporaryDirectory() as temp_dir:
            bin_dir = Path(temp_dir)
            python = bin_dir / "python3"
            python.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*"\n', encoding="utf-8")
            python.chmod(0o755)
            completed = subprocess.run(
                ["bash", str(entrypoint)],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"},
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout.strip(),
            "/usr/local/lib/algotrader/migrate_db.py --in-container "
            "--migrations-dir /docker-entrypoint-initdb.d/migrations",
        )


class MigrationApplicationTests(unittest.TestCase):
    def test_applies_the_exact_migration_content_that_was_loaded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "V001__host_version.sql"
            path.write_text("SELECT 'host-version';\n", encoding="utf-8")
            loaded = migrate_db.load_migrations(Path(temp_dir))[0]
            path.write_text("SELECT 'changed-after-load';\n", encoding="utf-8")
            psql = RecordingPsql()

            migrate_db.apply_migration(psql, loaded)

        applied_sql = psql.calls[0][0]
        self.assertIn("SELECT 'host-version';", applied_sql)
        self.assertNotIn("changed-after-load", applied_sql)
        self.assertNotIn("\\i /docker-entrypoint-initdb.d", applied_sql)


class ExistingDatabaseBaselineTests(unittest.TestCase):
    def test_baseline_records_only_versions_before_v003(self):
        psql = RecordingPsql()
        migrations = [migration(version) for version in range(1, 6)]

        with mock.patch.object(migrate_db, "current_schema_matches_v002", return_value=True):
            baselined = migrate_db.baseline_existing_database(psql, migrations)

        self.assertTrue(baselined)
        inserted_sql = psql.calls[0][0]
        self.assertIn("(1, 'migration_1', 'checksum-1')", inserted_sql)
        self.assertIn("(2, 'migration_2', 'checksum-2')", inserted_sql)
        self.assertNotIn("(3, 'migration_3', 'checksum-3')", inserted_sql)
        self.assertNotIn("(4, 'migration_4', 'checksum-4')", inserted_sql)
        self.assertNotIn("(5, 'migration_5', 'checksum-5')", inserted_sql)

    def test_schema_check_requires_current_closed_trade_shape(self):
        psql = RecordingPsql(["t"])

        self.assertTrue(migrate_db.current_schema_matches_v002(psql))

        schema_check = psql.calls[0][0]
        self.assertIn("('stop_loss_price')", schema_check)
        self.assertIn("('take_profit_price')", schema_check)
        self.assertIn("is_nullable = 'NO'", schema_check)
        self.assertIn("backtest_closed_trades_trade_direction_check", schema_check)
        self.assertIn("to_regclass('public.backtest_closed_trades')", schema_check)

    def test_main_applies_v003_and_later_after_baselining(self):
        migrations = [migration(version) for version in range(1, 6)]
        applied_v001_to_v002 = {item.version: (item.name, item.checksum) for item in migrations[:2]}
        psql = mock.Mock()
        lock = mock.Mock()

        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(migrate_db, "load_migrations", return_value=migrations)
            )
            stack.enter_context(
                mock.patch.object(
                    migrate_db,
                    "read_env_file",
                    side_effect=[
                        {"TIMESCALEDB_DB": "db", "TIMESCALEDB_USER": "user"},
                        {},
                    ],
                )
            )
            stack.enter_context(mock.patch.object(migrate_db, "Psql", return_value=psql))
            stack.enter_context(mock.patch.object(migrate_db, "create_ledger"))
            stack.enter_context(mock.patch.object(migrate_db, "acquire_lock", return_value=lock))
            release_lock = stack.enter_context(mock.patch.object(migrate_db, "release_lock"))
            stack.enter_context(
                mock.patch.object(
                    migrate_db,
                    "read_applied",
                    side_effect=[{}, applied_v001_to_v002],
                )
            )
            stack.enter_context(
                mock.patch.object(migrate_db, "baseline_existing_database", return_value=True)
            )
            apply_pending = stack.enter_context(mock.patch.object(migrate_db, "apply_pending"))

            self.assertEqual(migrate_db.main(), 0)

        apply_pending.assert_called_once_with(psql, migrations, applied_v001_to_v002)
        release_lock.assert_called_once_with(lock)


class MigrationLockTests(unittest.TestCase):
    def test_ledger_creation_does_not_create_a_persistent_lock_table(self):
        psql = RecordingPsql()

        migrate_db.create_ledger(psql)

        self.assertIn("schema_migrations", psql.calls[0][0])
        self.assertNotIn("schema_migration_runner_lock", psql.calls[0][0])

    def test_lock_uses_a_session_scoped_advisory_lock(self):
        process = mock.Mock()
        process.stdin = StringIO()
        process.stdout = StringIO("t\nmigration-lock-query-complete\n")
        process.wait.return_value = 0
        psql = mock.Mock()
        psql.command.return_value = ["psql"]

        with mock.patch.object(migrate_db.subprocess, "Popen", return_value=process):
            lock = migrate_db.acquire_lock(psql)
            written_sql = process.stdin.getvalue()
            self.assertIn("pg_try_advisory_lock", written_sql)
            migrate_db.release_lock(lock)

        self.assertTrue(process.stdin.closed)
        process.wait.assert_called_once()

    def test_busy_advisory_lock_rejects_the_runner(self):
        process = mock.Mock()
        process.stdin = StringIO()
        process.stdout = StringIO("f\nmigration-lock-query-complete\n")
        process.wait.return_value = 0
        psql = mock.Mock()
        psql.command.return_value = ["psql"]

        with mock.patch.object(migrate_db.subprocess, "Popen", return_value=process):
            with self.assertRaisesRegex(SystemExit, "already active"):
                migrate_db.acquire_lock(psql)

        self.assertTrue(process.stdin.closed)
        process.wait.assert_called_once()


if __name__ == "__main__":
    unittest.main()
