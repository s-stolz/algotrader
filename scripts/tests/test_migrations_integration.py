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
            db_name=migrate_db.require_config(shared_env, "TIMESCALEDB_DB"),
            db_user=migrate_db.require_config(shared_env, "TIMESCALEDB_USER"),
        )

    def setUp(self) -> None:
        self.schema = f"migration_test_{uuid.uuid4().hex}"
        self._run_psql(f"""
CREATE SCHEMA "{self.schema}";
CREATE TABLE "{self.schema}".backtest_runs (
    run_id VARCHAR(36) PRIMARY KEY
);
CREATE TABLE "{self.schema}".backtest_closed_trades (
    run_id VARCHAR(36) NOT NULL,
    trade_sequence INTEGER NOT NULL,
    trade_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(32) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    entry_timestamp_ms BIGINT NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_timestamp_ms BIGINT NOT NULL,
    exit_price DOUBLE PRECISION NOT NULL,
    realized_pnl DOUBLE PRECISION NOT NULL,
    fees DOUBLE PRECISION NOT NULL,
    exit_reason VARCHAR(32) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES "{self.schema}".backtest_runs (run_id)
        ON DELETE CASCADE,
    PRIMARY KEY (run_id, trade_sequence),
    CONSTRAINT uq_backtest_closed_trades_identity UNIQUE (run_id, trade_id),
    CONSTRAINT backtest_closed_trades_exit_reason_check
        CHECK (exit_reason IN ('signal', 'stop_loss', 'take_profit'))
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

    def _apply_v005_and_v006(self) -> subprocess.CompletedProcess[str]:
        return self._run_psql(
            f"""
BEGIN;
SET search_path TO "{self.schema}";
\\i {migrate_db.CONTAINER_MIGRATIONS_DIR}/V005__upgrade_legacy_closed_trades.sql
INSERT INTO schema_migrations (version) VALUES (5);
COMMIT;
BEGIN;
\\i {migrate_db.CONTAINER_MIGRATIONS_DIR}/V006__audit_closed_trades_schema.sql
INSERT INTO schema_migrations (version) VALUES (6);
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
        completed = self._apply_v005_and_v006()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self._column_state().splitlines(),
            ["stop_loss_price:YES", "take_profit_price:YES", "trade_direction:NO"],
        )
        self.assertEqual(self._ledger_count(), "2")

    def test_rejects_populated_directionless_table_and_rolls_back(self) -> None:
        self._run_psql(f"INSERT INTO \"{self.schema}\".backtest_runs VALUES ('legacy');")
        self._run_psql(
            f"""
INSERT INTO "{self.schema}".backtest_closed_trades VALUES (
    'legacy', 1, 'trade-1', 'EURUSD', 1.0, 1, 1.0, 2, 2.0, 1.0, 0.0, 'signal'
);
"""
        )

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Cannot safely infer trade_direction", completed.stderr)
        self.assertEqual(self._column_state(), "")
        self.assertEqual(self._ledger_count(), "0")

    def test_rejects_wrong_column_type_without_ledgering_v006(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades '
            "ALTER COLUMN quantity TYPE NUMERIC;"
        )

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(
            self._column_state().splitlines(),
            ["stop_loss_price:YES", "take_profit_price:YES", "trade_direction:NO"],
        )
        self.assertEqual(self._ledger_count(), "1")

    def test_completes_a_partial_nullable_protective_price_pair(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades '
            "ADD COLUMN stop_loss_price DOUBLE PRECISION;"
        )

        completed = self._apply_v005_and_v006()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            self._column_state().splitlines(),
            ["stop_loss_price:YES", "take_profit_price:YES", "trade_direction:NO"],
        )
        self.assertEqual(self._ledger_count(), "2")

    def test_rejects_missing_primary_key_without_ledgering_v006(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades '
            "DROP CONSTRAINT backtest_closed_trades_pkey;"
        )

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_incorrect_unique_key_without_ledgering_v006(self) -> None:
        self._run_psql(f"""
ALTER TABLE "{self.schema}".backtest_closed_trades
    DROP CONSTRAINT uq_backtest_closed_trades_identity;
ALTER TABLE "{self.schema}".backtest_closed_trades
    ADD CONSTRAINT uq_backtest_closed_trades_identity UNIQUE (run_id, symbol);
""")

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_non_cascading_run_foreign_key_without_ledgering_v006(self) -> None:
        self._run_psql(f"""
ALTER TABLE "{self.schema}".backtest_closed_trades
    DROP CONSTRAINT backtest_closed_trades_run_id_fkey;
ALTER TABLE "{self.schema}".backtest_closed_trades
    ADD FOREIGN KEY (run_id) REFERENCES "{self.schema}".backtest_runs (run_id);
""")

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_nullable_core_column_without_ledgering_v006(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades ALTER COLUMN fees DROP NOT NULL;'
        )

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_unexpected_column_without_ledgering_v006(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades ADD COLUMN legacy_note TEXT;'
        )

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_permissive_exit_reason_check_without_ledgering_v006(self) -> None:
        self._run_psql(f"""
ALTER TABLE "{self.schema}".backtest_closed_trades
    DROP CONSTRAINT backtest_closed_trades_exit_reason_check;
ALTER TABLE "{self.schema}".backtest_closed_trades
    ADD CONSTRAINT backtest_closed_trades_exit_reason_check
    CHECK (exit_reason IN ('signal', 'stop_loss', 'take_profit', 'other'));
""")

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_invalid_existing_direction_semantics_without_ledgering_v006(self) -> None:
        self._run_psql(f"""
ALTER TABLE "{self.schema}".backtest_closed_trades
    ADD COLUMN stop_loss_price DOUBLE PRECISION,
    ADD COLUMN take_profit_price DOUBLE PRECISION,
    ADD COLUMN trade_direction VARCHAR(8) NOT NULL;
ALTER TABLE "{self.schema}".backtest_closed_trades
    ADD CONSTRAINT backtest_closed_trades_trade_direction_check
    CHECK (trade_direction IN ('long', 'short', 'sideways'));
""")

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported backtest_closed_trades schema", completed.stderr)
        self.assertEqual(self._ledger_count(), "1")

    def test_rejects_unsupported_table_shape_without_ledgering(self) -> None:
        self._run_psql(
            f'ALTER TABLE "{self.schema}".backtest_closed_trades DROP COLUMN exit_reason;'
        )

        completed = self._apply_v005_and_v006()

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Unsupported legacy backtest_closed_trades table shape", completed.stderr)
        self.assertEqual(self._column_state(), "")
        self.assertEqual(self._ledger_count(), "0")


if __name__ == "__main__":
    unittest.main()
