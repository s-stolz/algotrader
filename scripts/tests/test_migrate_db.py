from __future__ import annotations

import hashlib
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


class MigrationChecksumTests(unittest.TestCase):
    def run_with_ledger(self, migrations, checksums):
        ledger = "\n".join(
            f"{item.version}|{item.name}|{checksum}"
            for item, checksum in zip(migrations, checksums)
        )
        psql = RecordingPsql(["", ledger])
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(migrate_db, "acquire_lock"))
            stack.enter_context(mock.patch.object(migrate_db, "release_lock"))
            migrate_db.run_migrations(psql, migrations)
        return psql

    def test_matching_checksums_apply_only_pending_migrations(self):
        migrations = migrate_db.load_migrations()[:4]
        psql = self.run_with_ledger(migrations, [item.checksum for item in migrations[:3]])
        mutations = [sql for sql, _ in psql.calls if "INSERT INTO schema_migrations" in sql]
        self.assertEqual(len(mutations), 1)
        self.assertIn(migrations[3].sql, mutations[0])
        self.assertNotIn("UPDATE schema_migrations", "\n".join(sql for sql, _ in psql.calls))

    def test_any_applied_content_difference_blocks_upgrade(self):
        migrations = migrate_db.load_migrations()
        for index, item in enumerate(migrations):
            for difference in ("trailing_blank", "sql"):
                with self.subTest(version=item.version, difference=difference):
                    applied_sql = item.sql + "\n"
                    if difference == "sql":
                        applied_sql = item.sql + "SELECT 42;\n"
                    checksums = [entry.checksum for entry in migrations]
                    checksums[index] = hashlib.sha256(applied_sql.encode()).hexdigest()
                    with self.assertRaisesRegex(SystemExit, "Checksum drift detected"):
                        self.run_with_ledger(migrations, checksums)


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


class DatabaseInitializationTests(unittest.TestCase):
    def run_with_empty_ledger(self, has_tables: bool):
        psql = RecordingPsql(["t" if has_tables else "f"])
        migrations = [migration(1)]
        with (
            mock.patch.object(migrate_db, "create_ledger"),
            mock.patch.object(migrate_db, "acquire_lock"),
            mock.patch.object(migrate_db, "release_lock") as release,
            mock.patch.object(migrate_db, "read_applied", return_value={}),
            mock.patch.object(migrate_db, "apply_pending") as apply,
        ):
            if has_tables:
                with self.assertRaisesRegex(SystemExit, "no migration history"):
                    migrate_db.run_migrations(psql, migrations)
                apply.assert_not_called()
            else:
                migrate_db.run_migrations(psql, migrations)
                apply.assert_called_once_with(psql, migrations, {})
            release.assert_called_once()

    def test_fresh_database_runs_full_migration_chain(self):
        self.run_with_empty_ledger(False)

    def test_existing_database_without_history_is_rejected_before_migration(self):
        self.run_with_empty_ledger(True)


class MigrationLockTests(unittest.TestCase):
    def test_ledger_creation_creates_schema_migrations(self):
        psql = RecordingPsql()

        migrate_db.create_ledger(psql)

        self.assertIn("schema_migrations", psql.calls[0][0])

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
