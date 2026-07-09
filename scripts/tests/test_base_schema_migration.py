import unittest
from pathlib import Path


LEGACY_UPGRADE_PATH = (
    Path(__file__).resolve().parents[2]
    / "timescaledb-init"
    / "migrations"
    / "V005__upgrade_legacy_closed_trades.sql"
)


class BaseSchemaMigrationTests(unittest.TestCase):
    def test_upgrades_supported_legacy_closed_trade_shapes(self):
        sql = LEGACY_UPGRADE_PATH.read_text(encoding="utf-8").lower()

        self.assertIn("add column if not exists stop_loss_price", sql)
        self.assertIn("add column if not exists take_profit_price", sql)
        self.assertIn("cannot safely infer trade_direction", sql)
        self.assertIn("alter column trade_direction set not null", sql)
        self.assertIn("unsupported legacy backtest_closed_trades table shape", sql)


if __name__ == "__main__":
    unittest.main()
