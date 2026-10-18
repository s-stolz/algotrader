"""Opt-in runner acceptance against a disposable Docker PostgreSQL/Timescale service."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

CONTAINER = os.getenv("RECOVERY_MIGRATION_TEST_CONTAINER")
USER = os.getenv("RECOVERY_MIGRATION_TEST_USER", "vibe10")
ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(CONTAINER, "Set RECOVERY_MIGRATION_TEST_CONTAINER for real runner checks")
class MigrationRunnerTests(unittest.TestCase):
    def setUp(self):
        assert CONTAINER is not None
        if not CONTAINER.startswith("vibe10r1-"):
            raise RuntimeError("Runner tests require an owned disposable vibe10r1-* container")
        self.container = CONTAINER
        self.database = "vibe10r1_" + uuid4().hex
        self.remote = "/tmp/" + self.database
        self.local = tempfile.TemporaryDirectory()
        self.folder = Path(self.local.name)
        self.inventory = self.folder / "migrations"
        self.inventory.mkdir()
        shutil.copy2(ROOT / "timescaledb-init/05-run-migrations.sh", self.folder / "run.sh")
        self.docker("exec", self.container, "createdb", "-U", USER, self.database)
        self.docker("exec", self.container, "mkdir", "-p", self.remote)
        self.addCleanup(self.cleanup)
        self.write(
            1,
            "initial",
            "CREATE TABLE marker (value INTEGER PRIMARY KEY);\n" "INSERT INTO marker VALUES (1);\n",
        )

    def cleanup(self):
        self.docker("exec", self.container, "dropdb", "-U", USER, self.database)
        self.docker("exec", self.container, "rm", "-rf", self.remote)
        self.local.cleanup()

    def docker(self, *arguments, check=True):
        return subprocess.run(["docker", *arguments], capture_output=True, text=True, check=check)

    def write(self, version, name, sql):
        path = self.inventory / f"V{version:03d}__{name}.sql"
        path.write_text(sql)
        return path

    def run_migrations(self, *, success=True, path=None):
        self.docker("exec", self.container, "rm", "-rf", self.remote + "/migrations")
        self.docker("cp", str(self.folder) + "/.", self.container + ":" + self.remote)
        arguments = [
            "exec",
            "-e",
            "TIMESCALEDB_DB=" + self.database,
            "-e",
            "POSTGRES_USER=" + USER,
            "-e",
            "MIGRATIONS_DIR=" + self.remote + "/migrations",
        ]
        if path:
            arguments.extend(["-e", "PATH=" + path])
        result = self.docker(*arguments, self.container, "sh", self.remote + "/run.sh", check=False)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def query(self, sql):
        return self.docker(
            "exec",
            self.container,
            "psql",
            "-X",
            "-At",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            USER,
            "-d",
            self.database,
            "-c",
            sql,
        ).stdout.strip()

    def assert_no_pending_sql(self, ledger_rows="1", marker_values="1"):
        self.assertEqual(self.query("SELECT count(*) FROM schema_migrations"), ledger_rows)
        self.assertEqual(
            self.query("SELECT string_agg(value::text, ',' ORDER BY value) FROM marker"),
            marker_values,
        )

    def add_pending(self, version=2):
        return self.write(version, "pending", f"INSERT INTO marker VALUES ({version});\n")

    def test_fresh_upgrade_and_identical_replay(self):
        self.run_migrations()
        self.add_pending()
        self.run_migrations()
        self.run_migrations()
        self.assert_no_pending_sql("2", "1,2")

    def test_missing_applied_file_rejects_before_pending_sql(self):
        self.run_migrations()
        applied = self.add_pending()
        self.run_migrations()
        applied.unlink()
        self.add_pending(3)
        self.run_migrations(success=False)
        self.assert_no_pending_sql("2", "1,2")

    def test_renamed_applied_file_is_missing_even_with_consecutive_inventory(self):
        self.run_migrations()
        (self.inventory / "V001__initial.sql").rename(self.inventory / "V001__renamed.sql")
        self.add_pending()
        result = self.run_migrations(success=False)
        self.assertIn("Applied migration missing from inventory", result.stderr)
        self.assert_no_pending_sql()

    def test_duplicate_version_rejects_before_pending_sql(self):
        self.run_migrations()
        self.add_pending()
        self.write(2, "duplicate", "INSERT INTO marker VALUES (22);\n")
        self.run_migrations(success=False)
        self.assert_no_pending_sql()

    def test_version_gap_rejects_before_pending_sql(self):
        self.run_migrations()
        self.add_pending(3)
        self.run_migrations(success=False)
        self.assert_no_pending_sql()

    def test_malformed_filename_rejects_before_pending_sql(self):
        self.run_migrations()
        self.add_pending()
        (self.inventory / "V003__Invalid-Name.sql").write_text("INSERT INTO marker VALUES (3);\n")
        self.run_migrations(success=False)
        self.assert_no_pending_sql()

    def test_checksum_drift_rejects_before_pending_sql(self):
        self.run_migrations()
        (self.inventory / "V001__initial.sql").write_text("INSERT INTO marker VALUES (99);\n")
        self.add_pending()
        result = self.run_migrations(success=False)
        self.assertIn("Applied migration checksum mismatch", result.stderr)
        self.assert_no_pending_sql()

    def test_applied_ledger_gap_rejects_before_pending_sql(self):
        self.run_migrations()
        self.add_pending()
        self.run_migrations()
        self.query("DELETE FROM schema_migrations WHERE name = 'V001__initial.sql'")
        self.add_pending(3)
        result = self.run_migrations(success=False)
        self.assertIn("Applied migration versions must form a consecutive prefix", result.stderr)
        self.assert_no_pending_sql("1", "1,2")

    def test_empty_inventory_rejects(self):
        self.run_migrations()
        (self.inventory / "V001__initial.sql").unlink()
        self.run_migrations(success=False)
        self.assert_no_pending_sql()

    def test_execute_snapshot_used_for_checksum_when_deployment_file_changes(self):
        original = (self.inventory / "V001__initial.sql").read_bytes()
        wrapper = self.folder / "bin"
        wrapper.mkdir()
        script = wrapper / "sha256sum"
        script.write_text(
            '#!/bin/sh\n/usr/bin/sha256sum "$@"\n'
            f"printf 'SELECT 1;\\n' > '{self.remote}/migrations/V001__initial.sql'\n"
        )
        script.chmod(0o755)
        self.run_migrations(path=self.remote + "/bin:/usr/local/bin:/usr/bin:/bin")
        self.assertEqual(self.query("SELECT to_regclass('marker')"), "marker")
        self.assert_no_pending_sql()
        self.assertEqual(
            self.query("SELECT checksum FROM schema_migrations"),
            hashlib.sha256(original).hexdigest(),
        )

    def test_shipped_recovery_migration_applies_and_replays_without_changing_pending(self):
        (self.inventory / "V001__initial.sql").unlink()
        shutil.copy2(
            ROOT / "timescaledb-init/migrations/V001__pending_recovery.sql", self.inventory
        )
        self.query(
            "CREATE TABLE markets (symbol_id INTEGER PRIMARY KEY); INSERT INTO markets VALUES(1)"
        )
        self.run_migrations()
        self.query(
            "INSERT INTO pending_recoveries VALUES "
            "(1, 'account', 'identity', 1, 60000, 179999, 'startup')"
        )
        self.run_migrations()
        self.assertEqual(
            self.query("SELECT next_ms || ',' || target_ms FROM pending_recoveries"), "60000,179999"
        )
        self.assertEqual(
            self.query("SELECT name FROM schema_migrations"), "V001__pending_recovery.sql"
        )
