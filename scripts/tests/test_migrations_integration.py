from __future__ import annotations

import os
import subprocess
import unittest
import uuid

import scripts.migrate_db as migrate_db

RUN_INTEGRATION_TESTS = os.environ.get("RUN_MIGRATION_INTEGRATION_TESTS") == "1"


@unittest.skipUnless(
    RUN_INTEGRATION_TESTS,
    "set RUN_MIGRATION_INTEGRATION_TESTS=1 to use the local TimescaleDB container",
)
class LegacyClosedTradesMigrationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        shared_env = migrate_db.read_env_file(migrate_db.SHARED_ENV_PATH)
        cls.psql = migrate_db.Psql(
            db_name=shared_env.get("TIMESCALEDB_DB") or "finance_data",
            db_user=shared_env.get("TIMESCALEDB_USER") or "postgres",
        )

    def setUp(self) -> None:
        self.schema = f"migration_test_{uuid.uuid4().hex}"
        self._run_psql(f"""
CREATE SCHEMA "{self.schema}";
CREATE TABLE "{self.schema}".backtest_closed_trades (
    run_id TEXT,
    trade_sequence INTEGER,
    trade_id TEXT,
    symbol TEXT,
    quantity DOUBLE PRECISION,
    entry_timestamp_ms BIGINT,
    entry_price DOUBLE PRECISION,
    exit_timestamp_ms BIGINT,
    exit_price DOUBLE PRECISION,
    realized_pnl DOUBLE PRECISION,
    fees DOUBLE PRECISION,
    exit_reason TEXT
);
CREATE TABLE "{self.schema}".schema_migrations (
    version INTEGER PRIMARY KEY
);
""")

    def tearDown(self) -> None:
        self._run_psql(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE;')

    def _run_psql(self, sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            self.psql.command(capture=True),
            input=sql,
            text=True,
            capture_output=True,
            cwd=migrate_db.ROOT_DIR,
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(completed.stderr or completed.stdout)
        return completed

    def _apply_v005(self) -> subprocess.CompletedProcess[str]:
        return self._run_psql(
            f"""
BEGIN;
SET search_path TO "{self.schema}";
\\i {migrate_db.CONTAINER_MIGRATIONS_DIR}/V005__upgrade_legacy_closed_trades.sql
INSERT INTO schema_migrations (version) VALUES (5);
COMMIT;
""",
            check=False,
        )

    def _column_state(self) -> str:
        completed = self._run_psql(f"""
SELECT column_name || ':' || is_nullable
FROM information_schema.columns
WHERE table_schema = '{self.schema}'
  AND table_name = 'backtest_closed_trades'
  AND column_name IN ('trade_direction', 'stop_loss_price', 'take_profit_price')
ORDER BY column_name;
""")
        return completed.stdout.strip()

    def _ledger_count(self) -> str:
        completed = self._run_psql(f'SELECT COUNT(*) FROM "{self.schema}".schema_migrations;')
        return completed.stdout.strip()

    def test_upgrades_an_empty_compatible_legacy_table(self) -> None:
        completed = self._apply_v005()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self._column_state().splitlines(),
            ["stop_loss_price:YES", "take_profit_price:YES", "trade_direction:NO"],
        )
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_populated_directionless_table_and_rolls_back(self) -> None:
        self._run_psql(
            f"INSERT INTO \"{self.schema}\".backtest_closed_trades (run_id) VALUES ('legacy');"
        )

        completed = self._apply_v005()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Cannot safely infer trade_direction", completed.stderr)
        self.assertEqual(self._column_state(), "")
        self.assertEqual(self._ledger_count(), "0")

    def test_rejects_unsupported_table_shape_without_ledgering(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades DROP COLUMN exit_reason;'
        )

        completed = self._apply_v005()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported legacy backtest_closed_trades table shape", completed.stderr)
        self.assertEqual(self._column_state(), "")
        self.assertEqual(self._ledger_count(), "0")


if __name__ == "__main__":
    unittest.main()
