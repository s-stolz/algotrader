import json
import unittest
from contextlib import ExitStack
from unittest.mock import patch

import numpy as np
import pandas as pd
from app.services.candle_cache import CandleCache
from app.services.historical_indicator_service import run_historical_indicator
from indicator_engine import BarTensor
from indicator_engine.indicators.currency_strength import CurrencyStrength

DAY = 86_400_000
STEP = 300_000
START = 20000 * DAY
ASSETS = CurrencyStrength.spec.required_assets or []


class HistoricalIndicatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.times = START + np.arange(-1, 300) * STEP
        random = np.random.default_rng(17)
        prices = np.exp(np.cumsum(random.normal(0, 0.001, (len(self.times), len(ASSETS))), axis=0))
        self.frames = {
            asset: pd.DataFrame(
                {
                    "open": prices[:, i],
                    "high": prices[:, i],
                    "low": prices[:, i],
                    "close": prices[:, i],
                    "volume": 1.0,
                },
                index=pd.to_datetime(self.times, unit="ms", utc=True),
            )
            for i, asset in enumerate(ASSETS)
        }
        self.calls = []
        tensor = CurrencyStrength().batch(
            BarTensor(prices[:, :, None], self.times, np.array(ASSETS), np.array(["close"])), {}
        )
        self.expected = pd.DataFrame(
            tensor.data[:, 0, :], index=self.times, columns=pd.Index(CurrencyStrength.spec.outputs)
        ).dropna()

    async def _fetch(self, *, symbol, timeframe, start_ms, end_ms, limit, exchange):
        self.calls.append(
            dict(
                symbol=symbol,
                timeframe=timeframe,
                start_ms=start_ms,
                end_ms=end_ms,
                limit=limit,
                exchange=exchange,
            )
        )
        frame = self.frames[symbol]
        if start_ms is not None:
            frame = frame.loc[frame.index >= pd.to_datetime(start_ms, unit="ms", utc=True)]
        if end_ms is not None:
            frame = frame.loc[frame.index < pd.to_datetime(end_ms, unit="ms", utc=True)]
        return frame.tail(limit) if limit is not None else frame.copy()

    async def _run(
        self,
        *,
        start: int | None = START,
        end: int | None = START + 300 * STEP,
        limit=None,
        indicator_id=5,
        params=None,
    ):
        with ExitStack() as stack:
            stack.enter_context(
                patch(
                    "app.services.anchored_indicator_service.get_candles", side_effect=self._fetch
                )
            )
            stack.enter_context(
                patch(
                    "app.services.historical_indicator_service.get_candles", side_effect=self._fetch
                )
            )
            response = await run_historical_indicator(
                indicator_id=indicator_id,
                symbol="EURUSD",
                exchange="test-exchange",
                timeframe="M5",
                start_ms=start,
                end_ms=end,
                limit=limit,
                custom_parameters=params or {},
                candle_cache=CandleCache(),
            )
        json.dumps(response, allow_nan=False)
        rows = response["data"]["indicator_data"]
        return pd.DataFrame(rows).set_index("timestamp_ms") if rows else pd.DataFrame()

    async def test_midday_request_matches_full_daily_calculation(self):
        start = START + 12 * 3_600_000
        end = START + 16 * 3_600_000
        result = await self._run(start=start, end=end)
        expected = self.expected.loc[(self.expected.index >= start) & (self.expected.index < end)]
        np.testing.assert_allclose(result, expected)
        self.assertEqual(result.index.tolist(), expected.index.tolist())
        self.assertTrue(all(call["exchange"] == "test-exchange" for call in self.calls))
        self.assertEqual({call["symbol"] for call in self.calls}, set(ASSETS))
        self.assertTrue(
            any(call["start_ms"] == START and call["limit"] is None for call in self.calls)
        )

    async def test_limit_only_expands_history_then_returns_original_window(self):
        end = START + 16 * 3_600_000
        result = await self._run(start=None, end=end, limit=20)
        expected = self.expected.loc[self.expected.index < end].tail(20)
        np.testing.assert_allclose(result, expected)
        self.assertEqual(result.index.tolist(), expected.index.tolist())
        self.assertEqual(len(self.calls), len(ASSETS) * 3)
        expanded = [c for c in self.calls if c["start_ms"] == START]
        self.assertEqual(len(expanded), len(ASSETS))
        self.assertTrue(all(c["limit"] is None for c in expanded))

    async def test_start_and_limit_do_not_truncate_anchor_history(self):
        end = START + 16 * 3_600_000
        result = await self._run(start=START + STEP, end=end, limit=12)
        expected = self.expected.loc[self.expected.index < end].tail(12)
        np.testing.assert_allclose(result, expected)
        self.assertEqual(result.index.tolist(), expected.index.tolist())

    async def test_paged_history_matches_the_same_full_day_slice(self):
        end = START + 16 * 3_600_000
        latest = await self._run(start=None, end=end, limit=20)
        earlier = await self._run(start=None, end=int(latest.index.to_numpy()[0]), limit=20)
        combined = pd.concat([earlier, latest])
        expected = self.expected.loc[self.expected.index < end].tail(40)
        self.assertEqual(combined.index.tolist(), expected.index.tolist())
        np.testing.assert_allclose(combined, expected)

    async def test_missing_input_preserves_earlier_values_and_recovers_next_day(self):
        gap = START + 10 * STEP
        self.frames[ASSETS[0]] = self.frames[ASSETS[0]].drop(
            pd.to_datetime(gap, unit="ms", utc=True)
        )
        result = await self._run()
        expected = self.expected.loc[
            (self.expected.index < gap) | (self.expected.index >= START + DAY)
        ]
        np.testing.assert_allclose(result, expected)
        self.assertEqual(result.index.tolist(), expected.index.tolist())
        self.assertTrue((await self._run(start=START + 12 * 3_600_000, end=START + DAY)).empty)

    async def test_gap_shared_by_all_sources_is_not_bridged(self):
        gap = START + 10 * STEP
        self.frames = {
            a: f.drop(pd.to_datetime(gap, unit="ms", utc=True)) for a, f in self.frames.items()
        }
        result = await self._run(end=START + DAY)
        self.assertEqual(
            result.index.tolist(), self.expected.loc[self.expected.index < gap].index.tolist()
        )

    async def test_limited_invalid_window_does_not_return_older_valid_values(self):
        self.frames[ASSETS[0]] = self.frames[ASSETS[0]].drop(
            pd.to_datetime(START + 10 * STEP, unit="ms", utc=True)
        )
        result = await self._run(start=None, end=START + 16 * 3_600_000, limit=20)
        self.assertTrue(result.empty)

    async def test_missing_predecessor_invalidates_first_day_only(self):
        self.frames[ASSETS[0]] = self.frames[ASSETS[0]].iloc[1:]
        result = await self._run()
        expected = self.expected.loc[self.expected.index >= START + DAY]
        np.testing.assert_allclose(result, expected)
        self.assertEqual(result.index.tolist(), expected.index.tolist())

    async def test_predecessors_can_have_different_timestamps_across_closures(self):
        frame = self.frames[ASSETS[0]].copy()
        frame.index = pd.to_datetime(
            np.concatenate(([START - 3 * DAY], self.times[1:])), unit="ms", utc=True
        )
        self.frames[ASSETS[0]] = frame
        result = await self._run()
        np.testing.assert_allclose(result, self.expected)
        self.assertEqual(result.index.tolist(), self.expected.index.tolist())

    async def test_missing_source_and_completely_empty_history_return_no_values(self):
        self.frames[ASSETS[0]] = self.frames[ASSETS[0]].iloc[:0]
        self.assertTrue((await self._run()).empty)
        self.frames = {a: f.iloc[:0] for a, f in self.frames.items()}
        self.assertTrue((await self._run()).empty)

    async def test_nonfinite_source_invalidates_remaining_day_without_invalid_json(self):
        self.frames[ASSETS[0]].loc[
            pd.to_datetime(START + 10 * STEP, unit="ms", utc=True), "close"
        ] = np.inf
        result = await self._run(end=START + DAY)
        self.assertEqual(len(result), 10)

    async def test_no_start_or_limit_returns_available_history(self):
        result = await self._run(start=None, end=None)
        np.testing.assert_allclose(result, self.expected)
        self.assertEqual(result.index.tolist(), self.expected.index.tolist())

    async def test_ordinary_rolling_indicator_keeps_existing_output(self):
        start = START + 4 * STEP
        end = START + 10 * STEP
        result = await self._run(start=start, end=end, indicator_id=1, params={"window": 3})
        expected = self.frames["EURUSD"].close.rolling(3).mean()
        expected = expected.loc[
            (expected.index >= pd.to_datetime(start, unit="ms", utc=True))
            & (expected.index < pd.to_datetime(end, unit="ms", utc=True))
        ]
        np.testing.assert_allclose(result["sma"], expected)
        self.assertEqual(len(self.calls), 1)
