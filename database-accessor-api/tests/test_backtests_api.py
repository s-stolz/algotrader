import asyncio
import os
import unittest
from datetime import datetime
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession

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


def _closed_trade_payload(**overrides):
    payload = {
        "trade_id": "trade-1",
        "symbol": "EURUSD",
        "quantity": 1000.0,
        "entry_timestamp_ms": 1714525200000,
        "entry_price": 1.0715,
        "exit_timestamp_ms": 1714532400000,
        "exit_price": 1.0740,
        "realized_pnl": 2.5,
        "fees": 0.15,
    }
    payload.update(overrides)
    return payload


class BacktestRunSummaryApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = InMemoryAsyncSession()

    def tearDown(self):
        self.session.close()

    @property
    def db(self) -> AsyncSession:
        return cast(AsyncSession, self.session)

    async def test_post_backtest_stores_summary_and_get_by_id_returns_it(self):
        saved = await main.create_backtest_summary(
            BacktestRunSummaryIn(**_summary_payload()),
            db=self.db,
        )

        fetched = await main.get_backtest_summary(saved["run_id"], db=self.db)

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
            db=self.db,
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
            db=self.db,
        )

        all_summaries = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id=None,
            engine=None,
            db=self.db,
        )
        symbol_matches = await main.list_backtest_summaries(
            symbol="EURUSD",
            timeframe=None,
            strategy_id=None,
            engine=None,
            db=self.db,
        )
        timeframe_matches = await main.list_backtest_summaries(
            symbol=None,
            timeframe="H1",
            strategy_id=None,
            engine=None,
            db=self.db,
        )
        strategy_matches = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id="breakout",
            engine=None,
            db=self.db,
        )
        engine_matches = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id=None,
            engine="event_driven",
            db=self.db,
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

    async def test_post_backtest_stores_closed_trades_for_separate_fetch(self):
        saved = await main.create_backtest_summary(
            BacktestRunSummaryIn(
                **_summary_payload(
                    trades=[
                        _closed_trade_payload(),
                        _closed_trade_payload(
                            trade_id="trade-2",
                            quantity=500.0,
                            entry_timestamp_ms=1714536000000,
                            entry_price=1.0750,
                            exit_timestamp_ms=1714543200000,
                            exit_price=1.0730,
                            realized_pnl=-1.0,
                            fees=0.1,
                        ),
                    ],
                )
            ),
            db=self.db,
        )

        trades = await main.get_backtest_trades(saved["run_id"], db=self.db)
        summaries = await main.list_backtest_summaries(
            symbol=None,
            timeframe=None,
            strategy_id=None,
            engine=None,
            db=self.db,
        )

        self.assertEqual(
            trades,
            [
                {
                    **_closed_trade_payload(),
                    "run_id": saved["run_id"],
                },
                {
                    **_closed_trade_payload(
                        trade_id="trade-2",
                        quantity=500.0,
                        entry_timestamp_ms=1714536000000,
                        entry_price=1.0750,
                        exit_timestamp_ms=1714543200000,
                        exit_price=1.0730,
                        realized_pnl=-1.0,
                        fees=0.1,
                    ),
                    "run_id": saved["run_id"],
                },
            ],
        )
        self.assertNotIn("trades", saved)
        self.assertNotIn("trades", summaries[0])

    async def test_post_backtest_with_no_closed_trades_returns_empty_trade_list(self):
        saved = await main.create_backtest_summary(
            BacktestRunSummaryIn(**_summary_payload(trade_count=0)),
            db=self.db,
        )

        trades = await main.get_backtest_trades(saved["run_id"], db=self.db)
        fetched = await main.get_backtest_summary(saved["run_id"], db=self.db)

        self.assertEqual(trades, [])
        self.assertEqual(fetched["trade_count"], 0)
        self.assertNotIn("trades", fetched)
