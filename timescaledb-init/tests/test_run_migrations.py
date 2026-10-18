"""Real recovery upgrades preserve the existing dev ledger and experiment history."""

import os
import subprocess
import unittest
from pathlib import Path
from uuid import uuid4

from scripts import migrate_db

CONTAINER = os.getenv("RECOVERY_MIGRATION_TEST_CONTAINER")
USER = os.getenv("RECOVERY_MIGRATION_TEST_USER", "recovery_test")
ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(CONTAINER, "Set RECOVERY_MIGRATION_TEST_CONTAINER for real runner checks")
class RecoveryMigrationTests(unittest.TestCase):
    def setUp(self):
        assert CONTAINER is not None
        if not CONTAINER.startswith("vibe10r1-"):
            raise RuntimeError("Runner tests require an owned disposable vibe10r1-* container")
        self.container = CONTAINER
        self.database = "vibe10r1_" + uuid4().hex
        self.docker("createdb", "-U", USER, self.database)
        self.addCleanup(self.docker, "dropdb", "-U", USER, self.database)
        outer = self

        class ContainerPsql(migrate_db.Psql):
            def command(self, *, capture=False):
                command = [
                    "docker",
                    "exec",
                    "-i",
                    outer.container,
                    "psql",
                    "-X",
                    "-q",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    USER,
                    "-d",
                    outer.database,
                ]
                if capture:
                    command.extend(["-At"])
                return command

        self.psql = ContainerPsql(self.database, USER)
        self.migrations = migrate_db.load_migrations()

    def docker(self, *arguments):
        return subprocess.run(
            ["docker", "exec", self.container, *arguments],
            capture_output=True,
            text=True,
            check=True,
        )

    def query(self, sql):
        return self.psql.run(sql, capture=True)

    def migrate(self, through=19):
        migrate_db.run_migrations(self.psql, self.migrations[:through])

    def test_dev_upgrade_keeps_applied_checksums_and_experiment_names(self):
        self.migrate(17)
        applied = migrate_db.read_applied(self.psql)
        self.query("""
INSERT INTO markets(symbol_id, symbol, exchange, market_type, min_move)
VALUES (1, 'BTC', 'TEST', 'crypto', 0.01);
INSERT INTO candles(symbol_id, timestamp_utc, open, high, low, close, volume)
VALUES (1, '2026-10-05Z', 1, 2, 1, 2, 3);
INSERT INTO backtest_runs(run_id, name, status, submitted_at, request_schema_version, request)
VALUES ('saved-run', 'Retained experiment', 'queued', now(), 2, '{"keep":"snapshot"}');
""")
        snapshot = self.query("SELECT row_to_json(r) FROM backtest_runs r WHERE run_id='saved-run'")
        self.migrate()
        self.migrate()
        final = migrate_db.read_applied(self.psql)
        self.assertEqual({v: final[v] for v in applied}, applied)
        self.assertEqual(len(final), 19)
        self.assertEqual(
            self.query("SELECT row_to_json(r) FROM backtest_runs r " "WHERE run_id='saved-run'"),
            snapshot,
        )
        self.assertEqual(self.query("SELECT close FROM candles WHERE symbol_id=1"), "2")
        self.assertEqual(self.query("SELECT count(*) FROM pending_recoveries"), "0")
        self.assertEqual(self.query("SELECT count(*) FROM live_write_guards"), "0")

    def test_pending_work_survives_guard_upgrade_and_replay(self):
        self.migrate(18)
        self.query("""
INSERT INTO markets(symbol_id, symbol, exchange, market_type, min_move)
VALUES (1, 'BTC', 'TEST', 'crypto', 0.01);
INSERT INTO pending_recoveries VALUES (1, 'account', 'identity', 1, 60000, 179999, 'startup');
""")
        self.migrate()
        self.query("INSERT INTO live_write_guards VALUES (1, 'account', 'batch', 60000)")
        self.migrate()
        self.assertEqual(self.query("SELECT boundary_ms FROM live_write_guards"), "60000")
        self.assertEqual(
            self.query("SELECT next_ms || ',' || target_ms " "FROM pending_recoveries"),
            "60000,179999",
        )
        self.assertEqual(len(migrate_db.read_applied(self.psql)), 19)

    def test_fresh_full_inventory_replays_without_checksum_drift(self):
        self.migrate()
        applied = migrate_db.read_applied(self.psql)
        self.migrate()
        self.assertEqual(migrate_db.read_applied(self.psql), applied)
        self.assertEqual(len(applied), 19)
