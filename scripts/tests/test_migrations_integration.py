from __future__ import annotations

import json
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

    def test_v017_migrates_names_once_preserving_history_and_snapshot_guards(self) -> None:
        v008 = (migrate_db.MIGRATIONS_DIR / "V008__immutable_backtest_batches.sql").read_text()
        self._run_psql(f"""
SET search_path TO "{self.schema}";
ALTER TABLE backtest_runs ADD COLUMN request JSONB;
ALTER TABLE backtest_runs ADD COLUMN request_schema_version INTEGER;
ALTER TABLE backtest_runs ADD COLUMN status TEXT DEFAULT 'succeeded';
ALTER TABLE backtest_runs ADD COLUMN metrics JSONB DEFAULT '{{"return": 3}}';
ALTER TABLE backtest_runs ADD COLUMN submitted_at TIMESTAMPTZ DEFAULT '2026-01-01Z';
{v008}
ALTER TABLE schema_migrations ADD COLUMN name TEXT;
ALTER TABLE schema_migrations ADD COLUMN checksum_sha256 CHAR(64);
ALTER TABLE schema_migrations ADD COLUMN applied_at TIMESTAMPTZ DEFAULT now();
INSERT INTO backtest_batches (batch_id, submission_id, accepted_at, definition_schema_version,
    accepted_definition, strategy_metadata, raw_count, member_count, excluded_count)
VALUES ('batch', 'submission', now(), 1,
    '{{"shared_request":{{"run_metadata":
      {{"name":"  Sweep  ","label":"Old label","keep":true}}}},"keep":"definition"}}',
    '{{"keep":"strategy"}}', 1, 1, 0);
INSERT INTO backtest_runs (run_id, request_schema_version, request, batch_id, member_ordinal)
VALUES ('member', 3,
    '{{"symbols":["EURUSD"],"strategy":{{"strategy_version":1}},
      "run_metadata":{{"name":"member name","label":"member label","keep":true}}}}',
    'batch', 0);
INSERT INTO backtest_batch_events (batch_id, revision, event_type, status, occurred_at)
VALUES ('batch', 0, 'accepted', 'queued', now());
""")
        cases = [
            ("named", {"name": "  Same  ", "label": "Secondary", "keep": [1, 2]}, "Same"),
            ("duplicate", {"name": "Same", "keep": 5}, "Same"),
            ("fallback", {"name": 12, "label": "  Label  ", "keep": True}, "Label"),
            ("blank", {"name": " ", "label": "", "keep": None}, None),
            ("invalid", {"name": "two\nlines", "label": "x" * 121}, None),
            ("limit", {"name": "😀" * 120}, "😀" * 120),
            ("unnamed", None, None),
        ]
        for run_id, metadata, _ in cases:
            request = {"symbols": ["EURUSD"], "run_metadata": metadata, "keep": "execution"}
            self._run_psql(f"""
INSERT INTO "{self.schema}".backtest_runs (run_id, request_schema_version, request)
VALUES ({migrate_db.sql_literal(run_id)}, 2, {migrate_db.sql_literal(json.dumps(request))}::jsonb);
""")
        self._run_psql(f"""
INSERT INTO "{self.schema}".backtest_closed_trades VALUES
('named', 0, 'trade', 'EURUSD', 1, 1000, 1, 2000, 2, 1, 0, 'signal');
""")

        def snapshot() -> dict:
            rows = self._run_psql(f"""
SELECT json_build_object('runs', (SELECT json_agg(row_to_json(r) ORDER BY run_id)
    FROM "{self.schema}".backtest_runs r),
    'batches', (SELECT json_agg(row_to_json(b)) FROM "{self.schema}".backtest_batches b),
    'trades', (SELECT json_agg(row_to_json(t)) FROM "{self.schema}".backtest_closed_trades t),
    'events', (SELECT json_agg(row_to_json(e)) FROM "{self.schema}".backtest_batch_events e));
""")
            return json.loads(rows.stdout)

        before = snapshot()
        migrations = migrate_db.load_migrations()
        applied = {m.version: (m.name, m.checksum) for m in migrations if m.version < 17}
        for version, (name, checksum) in applied.items():
            self._run_psql(
                f'INSERT INTO "{self.schema}".schema_migrations '
                f"(version, name, checksum_sha256) VALUES ({version}, "
                f"{migrate_db.sql_literal(name)}, {migrate_db.sql_literal(checksum)});"
            )

        outer = self

        class SchemaPsql(migrate_db.Psql):
            def run(self, sql: str, *, capture: bool = False) -> str:
                result = outer._run_psql(f'SET search_path TO "{outer.schema}";\n{sql}')
                return "\n".join(
                    line for line in result.stdout.splitlines() if line != "SET"
                ).strip()

        runner = SchemaPsql(db_name=self.psql.db_name, db_user=self.psql.db_user)
        migrate_db.apply_pending(runner, migrations, applied)
        after = snapshot()
        actual_applied = migrate_db.read_applied(runner)
        migrate_db.ensure_no_checksum_drift(actual_applied, migrations)
        migrate_db.apply_pending(runner, migrations, actual_applied)
        self.assertEqual(snapshot(), after)
        self.assertEqual(len(actual_applied), 17)
        expected_names = {run_id: name for run_id, _, name in cases} | {"member": None}
        for old, new in zip(before["runs"], after["runs"]):
            expected = dict(old)
            expected["name"] = expected_names[old["run_id"]]
            metadata = expected["request"].get("run_metadata")
            if isinstance(metadata, dict):
                metadata.pop("name", None)
                metadata.pop("label", None)
            self.assertEqual(new, expected)
        expected_batch = before["batches"][0]
        expected_batch["name"] = "Sweep"
        metadata = expected_batch["accepted_definition"]["shared_request"]["run_metadata"]
        metadata.pop("name")
        metadata.pop("label")
        self.assertEqual(after["batches"], [expected_batch])
        self.assertEqual(after["trades"], before["trades"])
        self.assertEqual(after["events"], before["events"])
        for sql in [
            "UPDATE backtest_runs SET request='{}' WHERE run_id='member'",
            "UPDATE backtest_runs SET name='Member' WHERE run_id='member'",
            "UPDATE backtest_runs SET name=' padded ' WHERE run_id='named'",
            "UPDATE backtest_batches SET name=E'two\\nlines' WHERE batch_id='batch'",
        ]:
            rejected = self._run_psql(f'SET search_path TO "{self.schema}"; {sql};', check=False)
            self.assertNotEqual(rejected.returncode, 0)

    def test_v007_preserves_successful_legacy_row_without_backfill(self) -> None:
        self._run_psql(
            f"INSERT INTO \"{self.schema}\".backtest_runs (run_id) VALUES ('legacy-success');"
        )
        migration = (migrate_db.MIGRATIONS_DIR / "V007__equity_replay_descriptor.sql").read_text()
        self._run_psql(f'SET search_path TO "{self.schema}";\n{migration}')
        row = self._run_psql(
            f"SELECT run_id || ':' || COALESCE(replay_descriptor::text, 'NULL') "
            f"FROM \"{self.schema}\".backtest_runs WHERE run_id = 'legacy-success';"
        )
        self.assertEqual(row.stdout.strip(), "legacy-success:NULL")

    def test_v008_preserves_legacy_run_and_guards_accepted_membership(self) -> None:
        migration = (migrate_db.MIGRATIONS_DIR / "V008__immutable_backtest_batches.sql").read_text()
        self._run_psql(f"""
ALTER TABLE "{self.schema}".backtest_runs ADD COLUMN request JSONB;
ALTER TABLE "{self.schema}".backtest_runs ADD COLUMN request_schema_version INTEGER;
INSERT INTO "{self.schema}".backtest_runs (run_id, request) VALUES ('legacy', '{{}}');
SET search_path TO "{self.schema}";
{migration}
""")
        legacy = self._run_psql(
            f"SELECT COALESCE(batch_id, 'standalone') FROM \"{self.schema}\".backtest_runs "
            "WHERE run_id = 'legacy';"
        )
        self.assertEqual(legacy.stdout.strip(), "standalone")
        self._run_psql(f"""
SET search_path TO "{self.schema}";
INSERT INTO backtest_batches (
    batch_id, submission_id, accepted_at, lifecycle_revision,
    definition_schema_version, accepted_definition, strategy_metadata,
    raw_count, member_count, excluded_count
) VALUES ('batch-1', 'submission-1', now(), 0, 1, '{{}}', '{{}}', 1, 1, 0);
INSERT INTO backtest_runs (run_id, request, request_schema_version, batch_id, member_ordinal)
VALUES (
    'member-1', '{{"symbols":["EURUSD"],"strategy":{{"strategy_version":1}}}}',
    3, 'batch-1', 0
);
INSERT INTO backtest_batch_events (batch_id, revision, event_type, status, occurred_at)
VALUES ('batch-1', 0, 'accepted', 'queued', now());
""")
        rejected_insert = self._run_psql(
            f"""
SET search_path TO "{self.schema}";
INSERT INTO backtest_runs (run_id, request, request_schema_version, batch_id, member_ordinal)
VALUES (
    'late-member', '{{"symbols":["EURUSD"],"strategy":{{"strategy_version":1}}}}',
    3, 'batch-1', 1
);
""",
            check=False,
        )
        self.assertNotEqual(rejected_insert.returncode, 0)
        self.assertIn("membership is immutable", rejected_insert.stderr)
        rejected_delete = self._run_psql(
            f"""
DELETE FROM "{self.schema}".backtest_runs WHERE run_id = 'member-1';
""",
            check=False,
        )
        self.assertNotEqual(rejected_delete.returncode, 0)
        retained = self._run_psql(f'SELECT COUNT(*) FROM "{self.schema}".backtest_runs;')
        self.assertEqual(retained.stdout.strip(), "2")
        prior_state_migration = (
            migrate_db.MIGRATIONS_DIR / "V012__backtest_batch_event_prior_status.sql"
        ).read_text()
        self._run_psql(f'SET search_path TO "{self.schema}";\n{prior_state_migration}')
        accepted = self._run_psql(
            f"SELECT event_type || ':' || status || ':' || COALESCE(prior_status, 'NULL') "
            f"FROM \"{self.schema}\".backtest_batch_events WHERE batch_id = 'batch-1';"
        )
        self.assertEqual(accepted.stdout.strip(), "accepted:queued:NULL")
        command_migration = (
            migrate_db.MIGRATIONS_DIR / "V013__backtest_batch_commands.sql"
        ).read_text()
        self._run_psql(f'SET search_path TO "{self.schema}";\n{command_migration}')
        self._run_psql(f"""SET search_path TO "{self.schema}";
INSERT INTO backtest_batch_commands
    (batch_id, command_id, command, status, lifecycle_revision, occurred_at)
VALUES ('batch-1', 'pause-1', 'pause', 'paused', 1, now());
""")
        duplicate = self._run_psql(
            f"""SET search_path TO "{self.schema}";
INSERT INTO backtest_batch_commands
    (batch_id, command_id, command, status, lifecycle_revision, occurred_at)
VALUES ('batch-1', 'pause-1', 'pause', 'paused', 1, now());
""",
            check=False,
        )
        self.assertNotEqual(duplicate.returncode, 0)
        cancellation_migration = (
            migrate_db.MIGRATIONS_DIR / "V015__backtest_batch_cancellation.sql"
        ).read_text()
        self._run_psql(f'SET search_path TO "{self.schema}";\n{cancellation_migration}')
        self._run_psql(f"""SET search_path TO "{self.schema}";
UPDATE backtest_batches
   SET cancel_requested_at=now(), cancellation_source='user',
       cancellation_reason='user_requested'
 WHERE batch_id='batch-1';
INSERT INTO backtest_batch_commands
    (batch_id, command_id, command, status, lifecycle_revision, occurred_at)
VALUES ('batch-1', 'cancel-1', 'cancel', 'cancelled', 2, now());
""")
        receipt = self._run_psql(
            f"SELECT command || ':' || status FROM \"{self.schema}\".backtest_batch_commands "
            "WHERE command_id='cancel-1';"
        )
        self.assertEqual(receipt.stdout.strip(), "cancel:cancelled")

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
        self._run_psql(f"""
INSERT INTO "{self.schema}".backtest_closed_trades VALUES (
    'legacy', 1, 'trade-1', 'EURUSD', 1.0, 1, 1.0, 2, 2.0, 1.0, 0.0, 'signal'
);
""")

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
