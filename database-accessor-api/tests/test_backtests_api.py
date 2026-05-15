import asyncio
import os
import unittest
from datetime import datetime

from sqlalchemy import create_engine

os.environ.setdefault("TIMESCALEDB_USER", "test")
os.environ.setdefault("TIMESCALEDB_PASSWORD", "test")
os.environ.setdefault("TIMESCALEDB_HOST", "localhost")
os.environ.setdefault("TIMESCALEDB_PORT", "5432")
os.environ.setdefault("TIMESCALEDB_DB", "test")

import main  # noqa: E402
from app.models import metadata  # noqa: E402
from app.schemas import BacktestRunSummaryIn  # noqa: E402


class InMemoryAsyncSession:
    def __init__(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        metadata.create_all(self.engine)
        self.connection = self.engine.connect()

    async def execute(self, statement, params=None):
        return self.connection.execute(statement, params or {})

    async def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()
        self.engine.dispose()


def _summary_payload(**overrides):
    payload = {
        "execution_duration_ms": 125,
        "symbol": "EURUSD",
        "timeframe": "M1",
        "engine": "vectorized",
        "strategy_id": "ema-cross",
        "start_ms": 1714521600000,
        "end_ms": 1714608000000,
        "initial_capital": 10000.0,
        "final_equity": 10450.25,
        "final_cash": 9450.25,
        "final_position_symbol": "EURUSD",
        "final_position_quantity": 1000.0,
        "total_return_pct": 4.5025,
        "max_drawdown_pct": 1.25,
        "trade_count": 3,
    }
    payload.update(overrides)
    return payload


class BacktestRunSummaryApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = InMemoryAsyncSession()

    def tearDown(self):
        self.session.close()

    async def test_post_backtest_stores_summary_and_get_by_id_returns_it(self):
        saved = await main.create_backtest_summary(
            BacktestRunSummaryIn(**_summary_payload()),
            db=self.session,
        )

        fetched = await main.get_backtest_summary(saved["run_id"], db=self.session)

        self.assertEqual(fetched["run_id"], saved["run_id"])
        self.assertIsInstance(fetched["persisted_at"], datetime)
        self.assertEqual(fetched["execution_duration_ms"], 125)
        self.assertEqual(fetched["symbol"], "EURUSD")
        self.assertEqual(fetched["timeframe"], "M1")
        self.assertEqual(fetched["engine"], "vectorized")
        self.assertEqual(fetched["strategy_id"], "ema-cross")
        self.assertEqual(fetched["start_ms"], 1714521600000)
        self.assertEqual(fetched["end_ms"], 1714608000000)
        self.assertEqual(fetched["initial_capital"], 10000.0)
        self.assertEqual(fetched["final_equity"], 10450.25)
        self.assertEqual(fetched["final_cash"], 9450.25)
        self.assertEqual(fetched["final_position_symbol"], "EURUSD")
        self.assertEqual(fetched["final_position_quantity"], 1000.0)
        self.assertEqual(fetched["total_return_pct"], 4.5025)
        self.assertEqual(fetched["max_drawdown_pct"], 1.25)
        self.assertEqual(fetched["trade_count"], 3)
        self.assertNotIn("trades", fetched)

    async def test_list_backtests_filters_summaries_and_orders_newest_first(self):
        older = await main.create_backtest_summary(
            BacktestRunSummaryIn(**_summary_payload(strategy_id="ema-cross")),
            db=self.session,
        )
        await asyncio.sleep(0.001)
        newer = await main.create_backtest_summary(
            BacktestRunSummaryIn(
                **_summary_payload(
                    symbol="GBPUSD",
                    timeframe="H1",
                    engine="event_driven",
                    strategy_id="breakout",
                    final_position_symbol=None,
                    final_position_quantity=0.0,
                )
            ),
            db=self.session,
        )

        all_summaries = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id=None,
            engine=None,
            db=self.session,
        )
        symbol_matches = await main.list_backtest_summaries(
            symbol="EURUSD",
            timeframe=None,
            strategy_id=None,
            engine=None,
            db=self.session,
        )
        timeframe_matches = await main.list_backtest_summaries(
            symbol=None,
            timeframe="H1",
            strategy_id=None,
            engine=None,
            db=self.session,
        )
        strategy_matches = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id="breakout",
            engine=None,
            db=self.session,
        )
        engine_matches = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id=None,
            engine="event_driven",
            db=self.session,
        )

        self.assertEqual(
            [row["run_id"] for row in all_summaries],
            [newer["run_id"], older["run_id"]],
        )
        self.assertEqual([row["run_id"] for row in symbol_matches], [older["run_id"]])
        self.assertEqual([row["run_id"] for row in timeframe_matches], [newer["run_id"]])
        self.assertEqual([row["run_id"] for row in strategy_matches], [newer["run_id"]])
        self.assertEqual([row["run_id"] for row in engine_matches], [newer["run_id"]])
        self.assertNotIn("trades", all_summaries[0])
