import unittest
from pathlib import Path

SCHEMA_AUDIT_PATH = (
    Path(__file__).resolve().parents[2]
    / "timescaledb-init"
    / "migrations"
    / "V006__audit_closed_trades_schema.sql"
)


class ClosedTradesSchemaAuditTests(unittest.TestCase):
    def test_audits_columns_keys_relationships_and_enum_checks(self):
        sql = SCHEMA_AUDIT_PATH.read_text(encoding="utf-8").lower()

        self.assertIn("expected_columns", sql)
        self.assertIn("constraints.contype = 'p'", sql)
        self.assertIn("constraints.contype = 'u'", sql)
        self.assertIn("constraints.contype = 'f'", sql)
        self.assertIn("constraints.confdeltype = 'c'", sql)
        self.assertIn("exit_reason", sql)
        self.assertIn("trade_direction", sql)
        self.assertIn("unsupported backtest_closed_trades schema", sql)


if __name__ == "__main__":
    unittest.main()
